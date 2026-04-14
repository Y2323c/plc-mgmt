#!/usr/bin/env python3
"""月次コーチングレポートスクリプト

毎月1日に以下3セクションを COACHING_COMPLETION_ROOM_ID へ送信する:
1. 前月のコーチング実施状況（コーチ別・対象者名・回数）
2. 今後31日以内にリマインドが発火する対象者
3. 追加コーチング（救済対象者）の現状

手動実行:
    cd /Users/Yuka/Desktop/Claude/Claude_code/data-analysis/PLC
    python3 scripts/monthly_report.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, datetime, timedelta
from collections import defaultdict

from utils.supabase_client import get_client
from utils.chatwork import send_message
from utils.secrets import get_secret
from utils.constants import LOG_TYPE_SESSION, COACHING_COMPLETION_ROOM_ID
from utils.date_helpers import parse_date
from utils.coaching_config import REMINDERS




def _section_prev_month(sb, today: date) -> str:
    """セクション①: 前月の実施状況"""
    if today.month == 1:
        prev_year, prev_month = today.year - 1, 12
    else:
        prev_year, prev_month = today.year, today.month - 1

    logs = (
        sb.table("coaching_logs")
        .select("ticket_id, session_count, session_date, coach_name")
        .eq("log_type", LOG_TYPE_SESSION)
        .execute()
        .data
    )

    prev_logs = [
        l for l in logs
        if l.get("session_date")
        and (d := parse_date(l["session_date"])) is not None
        and d.year == prev_year
        and d.month == prev_month
    ]

    title = f"■ 前月の実施状況（{prev_year}年{prev_month}月）"
    if not prev_logs:
        return title + "\n前月の実施はありませんでした。"

    # ticket_id → member_name のマッピング
    ticket_ids = list({l["ticket_id"] for l in prev_logs if l.get("ticket_id")})
    tickets_data = (
        sb.table("coaching_tickets")
        .select("id, name")
        .in_("id", ticket_ids)
        .execute()
        .data
    )
    ticket_name_map = {t["id"]: t["name"] for t in tickets_data}

    # コーチ別グループ化（日付昇順）
    by_coach: dict[str, list[str]] = defaultdict(list)
    for l in sorted(prev_logs, key=lambda x: x.get("session_date", "")):
        coach      = l.get("coach_name") or "（未設定）"
        member     = ticket_name_map.get(l["ticket_id"], "（不明）")
        session_d  = parse_date(l["session_date"])
        date_str   = session_d.strftime("%Y/%m/%d") if session_d else "—"
        num        = l.get("session_count")
        num_str    = f"{num}回目" if num is not None else "—"
        by_coach[coach].append(f"・ {member} — {num_str}（{date_str}）")

    lines = [title, ""]
    for coach, entries in sorted(by_coach.items()):
        lines.append(f"▼ {coach}（{len(entries)}件）")
        lines.extend(entries)
        lines.append("")
    return "\n".join(lines).rstrip()


def _section_upcoming(sb, today: date) -> str:
    """セクション②: 今後31日以内にリマインドが発火する対象者"""
    tickets = (
        sb.table("coaching_tickets")
        .select("*")
        .eq("is_active", 1)
        .eq("send_reminder", True)
        .in_("coaching_type", list(REMINDERS.keys()))
        .execute()
        .data
    )

    user_cache: dict[str, str | None] = {}
    upcoming = []

    for ticket in tickets:
        coaching_type = ticket.get("coaching_type", "")
        user_id       = ticket["user_id"]
        coach_name    = ticket.get("coach_name", "")
        ticket_id     = ticket["id"]
        member_name   = ticket.get("name", "")

        if coaching_type == "新規コーチング":
            if user_id not in user_cache:
                u = (
                    sb.table("users_master")
                    .select("joined_at")
                    .eq("id", user_id)
                    .maybe_single()
                    .execute()
                    .data
                )
                user_cache[user_id] = (u or {}).get("joined_at")
            ref_str = user_cache[user_id]
        else:
            ref_str = ticket.get("start_date")

        ref_date = parse_date(ref_str or "")
        if not ref_date:
            continue

        elapsed = (today - ref_date).days

        logs = (
            sb.table("coaching_logs")
            .select("session_count, session_date")
            .eq("ticket_id", ticket_id)
            .eq("log_type", LOG_TYPE_SESSION)
            .execute()
            .data
        )
        done_sessions = {
            l["session_count"] for l in logs
            if l.get("session_count") is not None
        }
        dates = [parse_date(l["session_date"]) for l in logs if l.get("session_date")]
        last_date = max((d for d in dates if d), default=None)
        last_str  = last_date.strftime("%Y/%m/%d") if last_date else "—"

        for reminder in REMINDERS[coaching_type]:
            reminder_day = reminder["day"]
            session_num  = reminder["session"]
            # 今後31日以内に発火 かつ 未消化
            if not (elapsed < reminder_day <= elapsed + 31):
                continue
            if session_num in done_sessions:
                continue
            remind_on = ref_date + timedelta(days=reminder_day)
            upcoming.append({
                "coach":       coach_name,
                "member":      member_name,
                "type":        coaching_type,
                "session_num": session_num,
                "remind_date": remind_on,
                "last_str":    last_str,
            })

    title = "■ 今後31日以内に日程調整が必要な対象者"
    if not upcoming:
        return title + "\n今後31日以内の対象者はいません。"

    by_coach: dict[str, list] = defaultdict(list)
    for u in sorted(upcoming, key=lambda x: x["remind_date"]):
        by_coach[u["coach"]].append(u)

    lines = [title + f"（{len(upcoming)}件）", ""]
    for coach, items in sorted(by_coach.items()):
        lines.append(f"▼ {coach}")
        for item in items:
            remind_str = item["remind_date"].strftime("%Y/%m/%d")
            lines.append(
                f"・ {item['member']} | {item['type']} {item['session_num']}回目"
                f" | リマインド日：{remind_str} | 最終コーチング：{item['last_str']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def _section_rescue(sb) -> str:
    """セクション③: 救済コーチング（救済対象者）"""
    tickets = (
        sb.table("coaching_tickets")
        .select("id, name, coach_name, start_date")
        .eq("is_active", 1)
        .eq("coaching_type", "救済コーチング")
        .execute()
        .data
    )

    title = "■ 救済コーチング（救済対象者）"
    if not tickets:
        return title + "\n救済対象者はいません。✅"

    by_coach: dict[str, list[str]] = defaultdict(list)
    for ticket in tickets:
        ticket_id   = ticket["id"]
        member_name = ticket.get("name") or "（不明）"
        coach_name  = ticket.get("coach_name") or "（未設定）"
        start_date  = parse_date(ticket.get("start_date", ""))
        start_disp  = start_date.strftime("%Y/%m/%d") if start_date else "—"

        logs = (
            sb.table("coaching_logs")
            .select("session_date")
            .eq("ticket_id", ticket_id)
            .eq("log_type", LOG_TYPE_SESSION)
            .execute()
            .data
        )
        total = len(logs)
        dates = [parse_date(l["session_date"]) for l in logs if l.get("session_date")]
        last_date = max((d for d in dates if d), default=None)
        last_str  = last_date.strftime("%Y/%m/%d") if last_date else "—"

        by_coach[coach_name].append(
            f"・ {member_name} | 開始：{start_disp} | 計{total}回 | 最終：{last_str}"
        )

    total_count = sum(len(v) for v in by_coach.values())
    lines = [title + f"（{total_count}件）", ""]
    for coach, entries in sorted(by_coach.items()):
        lines.append(f"▼ {coach}")
        lines.extend(entries)
        lines.append("")
    return "\n".join(lines).rstrip()


def _section_add_coaching(sb) -> str:
    """セクション④: 追加コーチング（有料）"""
    tickets = (
        sb.table("coaching_tickets")
        .select("id, name, coach_name, start_date")
        .eq("is_active", 1)
        .eq("coaching_type", "追加コーチング")
        .execute()
        .data
    )

    title = "■ 追加コーチング（有料）"
    if not tickets:
        return title + "\n対象者はいません。✅"

    by_coach: dict[str, list[str]] = defaultdict(list)
    for ticket in tickets:
        ticket_id   = ticket["id"]
        member_name = ticket.get("name") or "（不明）"
        coach_name  = ticket.get("coach_name") or "（未設定）"
        start_date  = parse_date(ticket.get("start_date", ""))
        start_disp  = start_date.strftime("%Y/%m/%d") if start_date else "—"

        logs = (
            sb.table("coaching_logs")
            .select("session_date")
            .eq("ticket_id", ticket_id)
            .eq("log_type", LOG_TYPE_SESSION)
            .execute()
            .data
        )
        total = len(logs)
        dates = [parse_date(l["session_date"]) for l in logs if l.get("session_date")]
        last_date = max((d for d in dates if d), default=None)
        last_str  = last_date.strftime("%Y/%m/%d") if last_date else "—"

        by_coach[coach_name].append(
            f"・ {member_name} | 開始：{start_disp} | 計{total}回 | 最終：{last_str}"
        )

    total_count = sum(len(v) for v in by_coach.values())
    lines = [title + f"（{total_count}件）", ""]
    for coach, entries in sorted(by_coach.items()):
        lines.append(f"▼ {coach}")
        lines.extend(entries)
        lines.append("")
    return "\n".join(lines).rstrip()


def run():
    sb    = get_client()
    today = date.today()
    token = get_secret("CHATWORK_COACHING_API_TOKEN")

    print(f"[{today}] 月次コーチングレポート生成開始")

    sections = []
    for label, func, args in [
        ("前月実施状況", _section_prev_month, (sb, today)),
        ("今後のリマインド", _section_upcoming, (sb, today)),
        ("救済コーチング", _section_rescue, (sb,)),
        ("追加コーチング", _section_add_coaching, (sb,)),
    ]:
        try:
            sections.append(func(*args))
        except Exception as e:
            print(f"  ⚠ {label}セクション生成エラー: {e}")
            sections.append(f"（{label}: 取得エラー）")

    year_month = f"{today.year}年{today.month}月"
    msg = "\n\n".join([f"【コーチング月次レポート】{year_month}"] + sections)

    ok = send_message(COACHING_COMPLETION_ROOM_ID, msg, token=token or None)
    status = "✅ 送信完了" if ok else "❌ 送信失敗"
    print(f"[{today}] {status}")


if __name__ == "__main__":
    run()
