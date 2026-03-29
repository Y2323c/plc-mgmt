import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta

from utils.supabase_client import get_client
from utils.chatwork import send_message
from utils.secrets import get_secret
from utils.constants import LOG_TYPE_SESSION, M_STATUS_CAT_COACH, COACHING_COMPLETION_ROOM_ID
from utils.style import apply_style

apply_style()

# ── リマインドスケジュール（coaching_reminder.py と同一定義）──────────────
REMINDERS = {
    "新規コーチング": [
        {"day": 140, "months": 5,  "session": 5},
        {"day": 230, "months": 8,  "session": 6},
        {"day": 320, "months": 11, "session": 7},
    ],
    "継続コーチング": [
        {"day":  80, "months": 3, "session": 1},
        {"day": 230, "months": 8, "session": 2},
    ],
}


def _parse_date(val: str) -> date | None:
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


def _status_label(elapsed: int, reminder_day: int, session_done: bool) -> str:
    if session_done:
        return "✅ 消化済み"
    days_until = reminder_day - elapsed
    if days_until > 0:
        return f"📅 あと{days_until}日"
    elif days_until == 0:
        return "🔔 今日"
    else:
        return f"⚠️ {abs(days_until)}日超過・未消化"


def _sort_key(label: str) -> int:
    if "超過" in label:
        n = int(label.replace("⚠️ ", "").split("日")[0])
        return -n
    if "今日" in label:
        return 0
    if "あと" in label:
        n = int(label.replace("📅 あと", "").replace("日", ""))
        return n
    return 9999


def _build_message(coaching_type: str, months: int, session_num: int,
                   member_name: str, coach_name: str) -> str:
    base = f"TO {coach_name}\nTO {member_name}\n"
    if coaching_type == "新規コーチング":
        return (
            base
            + f"あと10日で入会{months}ヶ月を迎えます。\n"
            + f"{session_num}回目のコーチングの日時の調整をお願いいたします。"
        )
    else:
        return (
            base
            + f"あと10日で継続{months}ヶ月を迎えます。\n"
            + f"{session_num}回目のコーチングの日時の調整をお願いいたします。\n"
            + "ローンチの状況に合わせて、2ヶ月以内を目安にコーチングを行なってください。"
        )


# ── データ取得 ───────────────────────────────────────────────────────────
st.title("コーチングリマインド確認")

sb    = get_client()
today = date.today()

# ── 全体キャンセル UI ─────────────────────────────────────────────────────
skip_data = (
    sb.table("reminder_skip_dates")
    .select("skip_date")
    .eq("skip_date", str(today))
    .execute()
    .data
)
skip_row = bool(skip_data)

with st.container(border=True):
    if skip_row:
        st.warning(f"⏸ 今日（{today.strftime('%Y/%m/%d')}）の自動送信はキャンセル済みです")
        if st.button("キャンセルを取り消す（自動送信を再開）"):
            sb.table("reminder_skip_dates").delete().eq("skip_date", str(today)).execute()
            st.rerun()
    else:
        col_s1, col_s2 = st.columns([3, 1])
        col_s1.info(f"▶️ 今日（{today.strftime('%Y/%m/%d')}）の自動送信：予定あり（18:00）")
        if col_s2.button("全キャンセル", use_container_width=True):
            sb.table("reminder_skip_dates").insert({"skip_date": str(today)}).execute()
            st.rerun()

st.divider()

# コーチ一覧（room_id も取得）
coaches_raw = (
    sb.table("m_status").select("label,room_id")
    .eq("category", M_STATUS_CAT_COACH).order("code").execute().data
)
all_coaches = [c["label"] for c in coaches_raw]
coach_rooms = {c["label"]: c.get("room_id") for c in coaches_raw}

# フィルター
col_f1, col_f2 = st.columns([2, 3])
with col_f1:
    coach_filter = st.selectbox("コーチで絞り込み", ["全コーチ"] + all_coaches)
with col_f2:
    status_filter = st.selectbox(
        "ステータスで絞り込み",
        ["すべて", "明日の送信予定", "要対応のみ（超過・今日）", "未消化のみ", "消化済みを除く"],
    )

# 有効チケット取得
tickets = (
    sb.table("coaching_tickets").select("*")
    .eq("is_active", 1)
    .eq("send_reminder", True)
    .in_("coaching_type", list(REMINDERS.keys()))
    .execute().data
)

# user_id → joined_at キャッシュ
user_ids = list({t["user_id"] for t in tickets if t.get("coaching_type") == "新規コーチング"})
user_cache: dict[str, str | None] = {}
if user_ids:
    users = (
        sb.table("users_master").select("id,joined_at")
        .in_("id", user_ids).execute().data
    )
    user_cache = {u["id"]: u.get("joined_at") for u in users}

# セッションログを一括取得
ticket_ids = [t["id"] for t in tickets]
all_logs = []
if ticket_ids:
    all_logs = (
        sb.table("coaching_logs").select("ticket_id,session_count")
        .in_("ticket_id", ticket_ids)
        .eq("log_type", LOG_TYPE_SESSION)
        .execute().data
    )
done_map: dict[str, set] = {}
for log in all_logs:
    tid = log["ticket_id"]
    sc  = log.get("session_count")
    if sc is not None:
        done_map.setdefault(tid, set()).add(sc)

# ── テーブル構築（pass 1）────────────────────────────────────────────────
rows = []
for ticket in tickets:
    coaching_type = ticket.get("coaching_type", "")
    coach_name    = ticket.get("coach_name", "")
    member_name   = ticket.get("name", "")
    ticket_id     = ticket["id"]

    if coach_filter != "全コーチ" and coach_name != coach_filter:
        continue

    if coaching_type == "新規コーチング":
        ref_str = user_cache.get(ticket["user_id"])
    else:
        ref_str = ticket.get("start_date")

    ref_date = _parse_date(ref_str or "")
    if not ref_date:
        ref_display = f"⚠️ 取得不可（{ref_str!r}）"
        elapsed = None
    else:
        ref_display = ref_date.strftime("%Y/%m/%d")
        elapsed = (today - ref_date).days

    done_sessions = done_map.get(ticket_id, set())

    for reminder in REMINDERS[coaching_type]:
        reminder_day = reminder["day"]
        session_num  = reminder["session"]
        months       = reminder["months"]
        session_done = session_num in done_sessions

        if elapsed is not None:
            status = _status_label(elapsed, reminder_day, session_done)
            remind_date_obj = ref_date + timedelta(days=reminder_day)
            remind_date     = remind_date_obj.strftime("%Y/%m/%d")
        else:
            status          = "⚠️ 基準日不明"
            remind_date     = "—"
            remind_date_obj = None

        rows.append({
            "_sort":            _sort_key(status) if elapsed is not None else 9998,
            "_months":          months,
            "_ticket_id":       ticket_id,
            "_session_num":     session_num,
            "_remind_date_raw": remind_date_obj,
            "スキップ":         False,   # pass 2 で上書き
            "名前":             member_name,
            "コーチ":           coach_name,
            "種別":             coaching_type,
            "基準日":           ref_display,
            "経過日数":         elapsed if elapsed is not None else "—",
            "対象回":           f"{session_num}回目",
            "リマインド日":     remind_date,
            "状況":             status,
        })

# ステータスフィルター
def _apply_status_filter(row: dict) -> bool:
    s = row["状況"]
    if status_filter == "すべて":
        return True
    if status_filter == "明日の送信予定":
        return s == "📅 あと1日"
    if status_filter == "要対応のみ（超過・今日）":
        return "超過" in s or "今日" in s
    if status_filter == "未消化のみ":
        return "消化済み" not in s
    if status_filter == "消化済みを除く":
        return "消化済み" not in s
    return True

rows = [r for r in rows if _apply_status_filter(r)]
rows.sort(key=lambda r: r["_sort"])

# ── スキップ状態を DB からロード（pass 2）────────────────────────────────
remind_dates = list({
    str(r["_remind_date_raw"]) for r in rows if r["_remind_date_raw"] is not None
})
if remind_dates:
    skip_targets = (
        sb.table("reminder_skip_targets")
        .select("skip_date,ticket_id,session_num")
        .in_("skip_date", remind_dates)
        .execute().data
    )
    skip_set = {(r["skip_date"], r["ticket_id"], r["session_num"]) for r in skip_targets}
    for r in rows:
        if r["_remind_date_raw"] is not None:
            r["スキップ"] = (str(r["_remind_date_raw"]), r["_ticket_id"], r["_session_num"]) in skip_set

# ── 表示 ─────────────────────────────────────────────────────────────────
st.caption(f"基準日: 本日 {today.strftime('%Y/%m/%d')} / 対象チケット数: {len(tickets)}")

if not rows:
    st.info("表示対象のリマインドはありません。")
else:
    display_cols = ["スキップ", "名前", "コーチ", "種別", "基準日", "経過日数", "対象回", "リマインド日", "状況"]
    df = pd.DataFrame([{k: r[k] for k in display_cols} for r in rows])

    edited_df = st.data_editor(
        df,
        column_config={
            "スキップ": st.column_config.CheckboxColumn("スキップ", default=False),
        },
        disabled=[col for col in display_cols if col != "スキップ"],
        hide_index=True,
        use_container_width=True,
        key="reminder_table",
    )

    col_b1, col_b2 = st.columns([1, 2])

    # スキップ保存ボタン
    if col_b1.button("スキップを保存", use_container_width=True):
        changed = 0
        for i, row in enumerate(rows):
            old_skip = row["スキップ"]
            new_skip = bool(edited_df.iloc[i]["スキップ"])
            if old_skip == new_skip or row["_remind_date_raw"] is None:
                continue
            skip_key = {
                "skip_date":   str(row["_remind_date_raw"]),
                "ticket_id":   row["_ticket_id"],
                "session_num": row["_session_num"],
            }
            if new_skip:
                sb.table("reminder_skip_targets").upsert(skip_key).execute()
            else:
                (sb.table("reminder_skip_targets").delete()
                 .eq("skip_date",   skip_key["skip_date"])
                 .eq("ticket_id",   skip_key["ticket_id"])
                 .eq("session_num", skip_key["session_num"])
                 .execute())
            changed += 1
        if changed:
            st.toast(f"スキップを保存しました（{changed}件）", icon="✅")
            st.rerun()
        else:
            st.toast("変更はありませんでした", icon="ℹ️")

    # 手動送信セクション
    st.divider()
    sendable = [r for r in rows if not r["スキップ"] and ("今日" in r["状況"] or "超過" in r["状況"])]
    if sendable:
        st.markdown("**📤 今日のリマインド送信対象**（スキップにチェックした人は除外済み）")
        for r in sendable:
            st.markdown(f"- {r['名前']}（{r['コーチ']}コーチ）｜{r['種別']} {r['_session_num']}回目 {r['状況']}")
        if st.button(f"リマインドを今すぐ送信（{len(sendable)}件）", type="primary"):
            token = get_secret("CHATWORK_COACHING_API_TOKEN")
            results = []
            for r in sendable:
                room_id = coach_rooms.get(r["コーチ"])
                if not room_id:
                    results.append(f"❌ {r['名前']}（{r['コーチ']}：room_id 未設定）")
                    continue
                msg = _build_message(r["種別"], r["_months"], r["_session_num"],
                                     r["名前"], r["コーチ"])
                ok  = send_message(str(room_id), msg, token=token or None)
                results.append(f"{'✅' if ok else '❌'} {r['名前']}（{r['コーチ']}コーチ）{r['_session_num']}回目")
                # 送信成功した行をスキップ登録（18:00の自動送信で二重送信しない）
                if ok and r["_remind_date_raw"] is not None:
                    sb.table("reminder_skip_targets").upsert({
                        "skip_date":   str(r["_remind_date_raw"]),
                        "ticket_id":   r["_ticket_id"],
                        "session_num": r["_session_num"],
                    }).execute()
            st.write("---")
            for line in results:
                st.write(line)
    else:
        st.caption("今日の送信対象はありません（全員スキップ済みか、対象なし）")

    # サマリー
    st.divider()
    overdue   = sum(1 for r in rows if "超過" in r["状況"])
    today_cnt = sum(1 for r in rows if "今日" in r["状況"])
    upcoming  = sum(1 for r in rows if "あと" in r["状況"])
    done      = sum(1 for r in rows if "消化済み" in r["状況"])
    skipped   = sum(1 for r in rows if r["スキップ"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("⚠️ 超過・未消化", overdue)
    c2.metric("🔔 今日送信",     today_cnt)
    c3.metric("📅 予定あり",     upcoming)
    c4.metric("✅ 消化済み",     done)
    c5.metric("📵 スキップ",     skipped)
