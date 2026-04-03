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

from datetime import date, datetime, timedelta

from utils.supabase_client import get_client
from utils.chatwork import send_message
from utils.secrets import get_secret
from utils.constants import LOG_TYPE_SESSION, COACHING_COMPLETION_ROOM_ID
from utils.date_helpers import parse_date
from utils.coaching_config import REMINDERS, build_reminder_message




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

        # send_reminder=False のチケットはリマインド送信をスキップ
        if not ticket.get("send_reminder", True):
            continue

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
        lines = [
            f"【明日のコーチングリマインド予定】{tomorrow.strftime('%Y/%m/%d')}",
            "",
            "明日のリマインド対象者はいません。",
        ]
    else:
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
    skip_data = (
        sb.table("reminder_skip_dates")
        .select("skip_date")
        .eq("skip_date", str(today))
        .execute()
        .data
    )
    if skip_data:
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

    # 人別スキップターゲットを取得
    skip_targets_data = (
        sb.table("reminder_skip_targets")
        .select("ticket_id,session_num")
        .eq("skip_date", str(today))
        .execute()
        .data
    )
    skip_target_set = {(r["ticket_id"], r["session_num"]) for r in skip_targets_data}

    # user_id → joined_at のキャッシュ（新規コーチング用）
    user_cache: dict[str, str | None] = {}

    sent_count = 0

    for ticket in tickets:
        coaching_type = ticket.get("coaching_type", "")
        user_id       = ticket["user_id"]
        coach_name    = ticket.get("coach_name", "")
        ticket_id     = ticket["id"]
        member_name   = ticket.get("name", "")

        # send_reminder=False のチケットはリマインド送信をスキップ
        if not ticket.get("send_reminder", True):
            print(f"  ✓ {member_name}: リマインド無効（旧制度）。スキップ。")
            continue

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

        ref_date = parse_date(ref_str or "")
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

            if (ticket_id, session_num) in skip_target_set:
                print(f"  ✓ {member_name}: {session_num}回目はスキップ対象。送信しません。")
                continue

            room_id = coach_rooms.get(coach_name)
            if not room_id:
                print(f"  ⚠ {coach_name}: room_id が未設定。スキップ。")
                continue

            msg = build_reminder_message(coaching_type, reminder["months"], session_num,
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
