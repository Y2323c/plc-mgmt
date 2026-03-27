#!/usr/bin/env python3
"""コーチングリマインドスクリプト

手動実行:
    cd /Users/Yuka/Desktop/Claude/Claude_code/data-analysis/PLC
    python3 scripts/coaching_reminder.py

動作:
    - 有効チケット（is_active=1）の新規・継続コーチングを全件チェック
    - 基準日からの経過日数がリマインド日と一致した場合
    - 対象セッションが未消化の場合のみ、コーチのグループチャットへ通知
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re
from datetime import date, datetime, timedelta

from utils.supabase_client import get_client
from utils.chatwork import send_message
from utils.secrets import get_secret
from utils.constants import LOG_TYPE_SESSION, COACHING_COMPLETION_ROOM_ID

# ── リマインドスケジュール ────────────────────────────────────────────────
# day    : 基準日からの経過日数（この日に送信）
# months : メッセージ内の「〇ヶ月」
# session: まだ実施されていないと判定するセッション番号

REMINDERS = {
    "新規コーチング": [
        {"day": 140, "months": 5,  "session": 5},  # 5ヶ月目に5回目
        {"day": 230, "months": 8,  "session": 6},  # 8ヶ月目に6回目
        {"day": 320, "months": 11, "session": 7},  # 11ヶ月目に7回目
    ],
    "継続コーチング": [
        {"day":  80, "months": 3, "session": 1},  # 4ヶ月目に1回目
        {"day": 230, "months": 8, "session": 2},  # 9ヶ月目に2回目
    ],
}


def _parse_date(val: str) -> date | None:
    """文字列を date に変換。YYYY/MM/DD・YYYY/MM・日本語形式に対応。"""
    if not val:
        return None
    for fmt in ("%Y/%m/%d", "%Y/%m"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", val)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"(\d{4})年(\d{1,2})月", val)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    return None


def _build_message(coaching_type: str, months: int, session_num: int,
                   member_name: str, coach_name: str) -> str:
    """リマインドメッセージ本文を生成する。"""
    base = (
        f"TO {coach_name}\n"
        f"TO {member_name}\n"
    )
    if coaching_type == "新規コーチング":
        return (
            base
            + f"あと10日で入会{months}ヶ月を迎えます。\n"
            + f"{session_num}回目のコーチングの日時の調整をお願いいたします。"
        )
    else:  # 継続コーチング
        return (
            base
            + f"あと10日で継続{months}ヶ月を迎えます。\n"
            + f"{session_num}回目のコーチングの日時の調整をお願いいたします。\n"
            + "ローンチの状況に合わせて、2ヶ月以内を目安にコーチングを行なってください。"
        )


def _collect_targets(sb, check_date: date) -> list[dict]:
    """check_date の経過日数でリマインドが発火するターゲットを収集して返す。"""
    coach_rows = (
        sb.table("m_status")
        .select("label,room_id")
        .eq("category", "coach")
        .execute()
        .data
    )
    coach_rooms = {row["label"]: row.get("room_id") for row in coach_rows}

    tickets = (
        sb.table("coaching_tickets")
        .select("*")
        .eq("is_active", 1)
        .in_("coaching_type", list(REMINDERS.keys()))
        .execute()
        .data
    )

    user_cache: dict[str, str | None] = {}
    targets = []

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

        ref_date = _parse_date(ref_str or "")
        if not ref_date:
            continue

        elapsed = (check_date - ref_date).days

        logs = (
            sb.table("coaching_logs")
            .select("session_count")
            .eq("ticket_id", ticket_id)
            .eq("log_type", LOG_TYPE_SESSION)
            .execute()
            .data
        )
        done_sessions = {
            l["session_count"] for l in logs
            if l.get("session_count") is not None
        }

        for reminder in REMINDERS[coaching_type]:
            if elapsed != reminder["day"]:
                continue
            session_num = reminder["session"]
            if session_num in done_sessions:
                continue
            targets.append({
                "member_name":   member_name,
                "coach_name":    coach_name,
                "coaching_type": coaching_type,
                "session_num":   session_num,
                "months":        reminder["months"],
                "room_id":       coach_rooms.get(coach_name),
            })

    return targets


def run_preview(sb, today: date, token: str):
    """翌日のリマインド対象者を管理ルームへ通知する。"""
    tomorrow = today + timedelta(days=1)
    targets  = _collect_targets(sb, tomorrow)

    if not targets:
        print(f"[{today}] 明日のリマインド対象なし。通知をスキップ。")
        return

    lines = [
        f"【明日のコーチングリマインド予定】{tomorrow.strftime('%Y/%m/%d')}",
        "",
        f"以下の方へ明日リマインドを送信します（計{len(targets)}件）：",
        "",
    ]
    for t in targets:
        lines.append(
            f"・ {t['member_name']}（担当：{t['coach_name']}コーチ）"
            f"｜{t['coaching_type']} {t['session_num']}回目"
        )
    lines += [
        "",
        "問題がある場合は送信前に Streamlit の「コーチングリマインド確認」ページで対応してください。",
    ]

    msg = "\n".join(lines)
    ok  = send_message(COACHING_COMPLETION_ROOM_ID, msg, token=token or None)
    status = "✅ 送信" if ok else "❌ 失敗"
    print(f"[{today}] 前日通知 {status}（対象: {len(targets)}件）")


def run():
    sb = get_client()
    today = date.today()
    token = get_secret("CHATWORK_COACHING_API_TOKEN")

    print(f"[{today}] コーチングリマインド実行開始")

    # スキップフラグ確認
    skip_row = (
        sb.table("reminder_skip_dates")
        .select("skip_date")
        .eq("skip_date", str(today))
        .maybe_single()
        .execute()
        .data
    )
    if skip_row:
        print(f"[{today}] スキップフラグあり。送信をキャンセルします。")
        return

    # コーチ別 Chatwork グループ room_id を取得
    coach_rows = (
        sb.table("m_status")
        .select("label,room_id")
        .eq("category", "coach")
        .execute()
        .data
    )
    coach_rooms = {row["label"]: row.get("room_id") for row in coach_rows}

    # 有効な新規・継続チケットを全件取得
    tickets = (
        sb.table("coaching_tickets")
        .select("*")
        .eq("is_active", 1)
        .in_("coaching_type", list(REMINDERS.keys()))
        .execute()
        .data
    )
    print(f"  対象チケット数: {len(tickets)}")

    # user_id → joined_at のキャッシュ（新規コーチング用）
    user_cache: dict[str, str | None] = {}

    sent_count = 0

    for ticket in tickets:
        coaching_type = ticket.get("coaching_type", "")
        user_id       = ticket["user_id"]
        coach_name    = ticket.get("coach_name", "")
        ticket_id     = ticket["id"]
        member_name   = ticket.get("name", "")

        # 基準日を取得
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
        else:  # 継続コーチング
            ref_str = ticket.get("start_date")

        ref_date = _parse_date(ref_str or "")
        if not ref_date:
            print(f"  ⚠ {member_name}: 基準日が取得できません（{ref_str!r}）。スキップ。")
            continue

        elapsed = (today - ref_date).days

        # 実施済みセッション番号を取得
        logs = (
            sb.table("coaching_logs")
            .select("session_count")
            .eq("ticket_id", ticket_id)
            .eq("log_type", LOG_TYPE_SESSION)
            .execute()
            .data
        )
        done_sessions = {
            l["session_count"] for l in logs
            if l.get("session_count") is not None
        }

        # リマインドチェック
        for reminder in REMINDERS[coaching_type]:
            if elapsed != reminder["day"]:
                continue

            session_num = reminder["session"]
            if session_num in done_sessions:
                print(f"  ✓ {member_name}: {session_num}回目は消化済み。スキップ。")
                continue

            room_id = coach_rooms.get(coach_name)
            if not room_id:
                print(f"  ⚠ {coach_name}: room_id が未設定。スキップ。")
                continue

            msg = _build_message(coaching_type, reminder["months"], session_num,
                                 member_name, coach_name)
            ok = send_message(str(room_id), msg, token=token or None)
            status = "✅ 送信" if ok else "❌ 失敗"
            print(
                f"  {status} → {coach_name}グループ | "
                f"{member_name} {session_num}回目 ({coaching_type})"
            )
            if ok:
                sent_count += 1

    print(f"完了: {sent_count}件送信")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="コーチングリマインドスクリプト")
    parser.add_argument("--preview", action="store_true",
                        help="翌日の対象者を管理ルームへ通知する（前日確認用）")
    args = parser.parse_args()

    _sb    = get_client()
    _today = date.today()
    _token = get_secret("CHATWORK_COACHING_API_TOKEN")

    if args.preview:
        run_preview(_sb, _today, _token)
    else:
        run()
