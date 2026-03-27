import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re
import streamlit as st
import pandas as pd
from datetime import date, datetime

from utils.supabase_client import get_client
from utils.constants import LOG_TYPE_SESSION, M_STATUS_CAT_COACH
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
    """ソート用: 超過 → 今日 → 近い順 → 消化済み"""
    if "超過" in label:
        # 超過日数を負値として扱う（-1 が最も緊急）
        n = int(label.replace("⚠️ ", "").split("日")[0])
        return -n
    if "今日" in label:
        return 0
    if "あと" in label:
        n = int(label.replace("📅 あと", "").replace("日", ""))
        return n
    return 9999  # 消化済みは最後


# ── データ取得 ───────────────────────────────────────────────────────────
st.title("コーチングリマインド確認")

sb = get_client()
today = date.today()

# コーチ一覧
coaches_raw = (
    sb.table("m_status").select("label")
    .eq("category", M_STATUS_CAT_COACH).order("code").execute().data
)
all_coaches = [c["label"] for c in coaches_raw]

# フィルター
col_f1, col_f2 = st.columns([2, 3])
with col_f1:
    coach_filter = st.selectbox("コーチで絞り込み", ["全コーチ"] + all_coaches)
with col_f2:
    status_filter = st.selectbox(
        "ステータスで絞り込み",
        ["すべて", "要対応のみ（超過・今日）", "未消化のみ", "消化済みを除く"],
    )

# 有効チケット取得
tickets = (
    sb.table("coaching_tickets").select("*")
    .eq("is_active", 1)
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

# チケットIDリスト → セッションログを一括取得
ticket_ids = [t["id"] for t in tickets]
all_logs = []
if ticket_ids:
    all_logs = (
        sb.table("coaching_logs").select("ticket_id,session_count")
        .in_("ticket_id", ticket_ids)
        .eq("log_type", LOG_TYPE_SESSION)
        .execute().data
    )
# ticket_id → 消化済みセッション番号セット
done_map: dict[str, set] = {}
for log in all_logs:
    tid = log["ticket_id"]
    sc  = log.get("session_count")
    if sc is not None:
        done_map.setdefault(tid, set()).add(sc)

# ── テーブル構築 ─────────────────────────────────────────────────────────
rows = []
for ticket in tickets:
    coaching_type = ticket.get("coaching_type", "")
    coach_name    = ticket.get("coach_name", "")
    member_name   = ticket.get("name", "")
    ticket_id     = ticket["id"]

    if coach_filter != "全コーチ" and coach_name != coach_filter:
        continue

    # 基準日
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
            remind_date = (ref_date + pd.Timedelta(days=reminder_day)).strftime("%Y/%m/%d")
        else:
            status = "⚠️ 基準日不明"
            remind_date = "—"

        rows.append({
            "_sort":        _sort_key(status) if elapsed is not None else 9998,
            "名前":         member_name,
            "コーチ":       coach_name,
            "種別":         coaching_type,
            "基準日":       ref_display,
            "経過日数":     elapsed if elapsed is not None else "—",
            "対象回":       f"{session_num}回目",
            "リマインド日": remind_date,
            "状況":         status,
        })

# ステータスフィルター
def _apply_status_filter(row: dict) -> bool:
    s = row["状況"]
    if status_filter == "すべて":
        return True
    if status_filter == "要対応のみ（超過・今日）":
        return "超過" in s or "今日" in s
    if status_filter == "未消化のみ":
        return "消化済み" not in s
    if status_filter == "消化済みを除く":
        return "消化済み" not in s
    return True

rows = [r for r in rows if _apply_status_filter(r)]
rows.sort(key=lambda r: r["_sort"])

# ── 表示 ─────────────────────────────────────────────────────────────────
st.caption(f"基準日: 本日 {today.strftime('%Y/%m/%d')} / 対象チケット数: {len(tickets)}")

if not rows:
    st.info("表示対象のリマインドはありません。")
else:
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "_sort"} for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # サマリー
    st.divider()
    total     = len(rows)
    overdue   = sum(1 for r in rows if "超過" in r["状況"])
    today_cnt = sum(1 for r in rows if "今日" in r["状況"])
    upcoming  = sum(1 for r in rows if "あと" in r["状況"])
    done      = sum(1 for r in rows if "消化済み" in r["状況"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⚠️ 超過・未消化", overdue)
    c2.metric("🔔 今日送信",     today_cnt)
    c3.metric("📅 予定あり",     upcoming)
    c4.metric("✅ 消化済み",     done)
