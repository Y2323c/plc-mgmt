import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import defaultdict
from datetime import date
import streamlit as st
import pandas as pd
from utils.supabase_client import get_client
from utils.constants import M_STATUS_CAT_COACH, LOG_TYPE_SESSION

st.title("コーチング進捗")

sb = get_client()

# コーチ一覧
_coaches_raw = (
    sb.table("m_status")
    .select("label")
    .eq("category", M_STATUS_CAT_COACH)
    .order("code")
    .execute()
    .data
)
COACH_LIST = [c["label"] for c in _coaches_raw if c["label"] != ".準備中"]

# コーチ選択（URLパラメータ対応）
param_coach = st.query_params.get("coach")
ALL_COACHES = "（全コーチ）"
coach_options = [ALL_COACHES] + COACH_LIST
_default_idx = coach_options.index(param_coach) if param_coach in coach_options else 0

selected_coach = st.selectbox("コーチを選択", coach_options, index=_default_idx)

# チケット取得（is_active=1 のみ）
ticket_query = sb.table("coaching_tickets").select("*").eq("is_active", 1)
if selected_coach != ALL_COACHES:
    ticket_query = ticket_query.eq("coach_name", selected_coach)
tickets = ticket_query.order("coach_name").execute().data

if not tickets:
    st.info("有効なチケットがありません。")
    st.stop()

# ユーザー名取得
user_ids = list({t["user_id"] for t in tickets})
members_raw = (
    sb.table("name_mappings")
    .select("user_id, clean_name")
    .in_("user_id", user_ids)
    .execute()
    .data
)
uid_to_name = {m["user_id"]: m["clean_name"] for m in members_raw}

# セッションログ一括取得
ticket_ids = [t["id"] for t in tickets]
logs_raw = (
    sb.table("coaching_logs")
    .select("ticket_id, log_type, session_date, next_session_date, session_count")
    .in_("ticket_id", ticket_ids)
    .eq("log_type", LOG_TYPE_SESSION)
    .order("session_date")
    .execute()
    .data
)

# ticket_id → logs マップ
ticket_logs: dict[str, list] = defaultdict(list)
for l in logs_raw:
    ticket_logs[l["ticket_id"]].append(l)

today = date.today()


def _days_since(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        d = date.fromisoformat(date_str.replace("/", "-"))
        return (today - d).days
    except Exception:
        return None


# 進捗テーブル構築
rows = []
for t in tickets:
    logs = ticket_logs[t["id"]]
    session_count = len(logs)
    last_date = logs[-1]["session_date"] if logs else None
    next_date = logs[-1].get("next_session_date") if logs else None
    elapsed = _days_since(last_date)
    max_sessions = t.get("max_sessions") or 0

    rows.append({
        "コーチ": t.get("coach_name") or "",
        "名前": uid_to_name.get(t["user_id"], ""),
        "種別": t.get("coaching_type") or "",
        "回数": f"{session_count} / {max_sessions}" if max_sessions else str(session_count),
        "最終セッション日": last_date or "—",
        "経過日数": elapsed if elapsed is not None else "—",
        "次回予定日": next_date or "—",
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# ─── 月別セッション実施数 ───────────────────────────
st.divider()
st.subheader("月別セッション実施数")

if logs_raw:
    monthly: dict[str, int] = defaultdict(int)
    for l in logs_raw:
        d = (l.get("session_date") or "")[:7]  # "YYYY/MM" or "YYYY-MM"
        if len(d) == 7:
            ym = d.replace("/", "-")  # 統一: YYYY-MM
            monthly[ym] += 1

    if monthly:
        monthly_df = pd.DataFrame(
            sorted(monthly.items(), reverse=True),
            columns=["年月", "実施数"],
        )
        st.dataframe(monthly_df, use_container_width=True, hide_index=True)
    else:
        st.info("セッション記録がありません。")
else:
    st.info("セッション記録がありません。")
