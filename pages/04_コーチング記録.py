import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
from datetime import date
import streamlit as st
import pandas as pd
from utils.supabase_client import get_client, insert_record
from utils.ui_helpers import member_selectbox
from utils.constants import M_STATUS_CAT_COACH, LOG_TYPE_SESSION

st.title("コーチング記録")

if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"), icon="✅")

sb = get_client()

# --- コーチ一覧取得 ---
_coaches_raw = sb.table("m_status").select("label").eq("category", M_STATUS_CAT_COACH).order("code").execute().data
COACH_LIST = [c["label"] for c in _coaches_raw]

# --- サイドバー ---
with st.sidebar:
    st.header("会員選択")
    selected_member = member_selectbox(key="member_coaching", show_all_key="show_all_coaching")
    if selected_member is None:
        st.info("会員を選択してください")
        st.stop()

# --- チケット選択 ---
tickets = sb.table("coaching_tickets").select("*").eq("user_id", selected_member["id"]).order("term_count").execute().data

st.subheader(f"{selected_member['display_name']}")

if not tickets:
    st.warning("チケットがありません。先にコーチングチケットを登録してください。")
    st.stop()

ticket_labels = [f"{t['term_count']}期 — {t.get('coaching_type') or '種別なし'}（{t.get('coach_name') or 'コーチ未定'}）{'✓' if t['is_active'] else ''}" for t in tickets]
ticket_idx = st.selectbox("チケット選択", range(len(tickets)), format_func=lambda i: ticket_labels[i])
selected_ticket = tickets[ticket_idx]

# --- セッション一覧 ---
logs = sb.table("coaching_logs").select("*").eq("ticket_id", selected_ticket["id"]).order("session_count").execute().data

session_count_total = sum(1 for l in logs if l.get("log_type") == LOG_TYPE_SESSION)
st.subheader(f"{selected_ticket['term_count']}期 記録（セッション{session_count_total}回 / 全{len(logs)}件）")

if logs:
    df = pd.DataFrame([{
        "種別": "セッション" if l.get("log_type") == LOG_TYPE_SESSION else "メモ",
        "回": l["session_count"] or "",
        "セッション日": l["session_date"] or "",
        "次回予定": l["next_session_date"] or "",
        "コーチ": l["coach_name"] or "",
        "メモ": (l["note"] or "")[:50] + ("…" if len(l["note"] or "") > 50 else ""),
        "_id": l["id"],
    } for l in logs])
    st.dataframe(df.drop(columns=["_id"]), use_container_width=True)
else:
    st.info("記録がありません")

# --- 追加フォーム ---
st.divider()
next_session = session_count_total + 1
st.subheader(f"第{next_session}回 セッション記録を追加")

with st.form("coaching_log_form"):
    col1, col2 = st.columns(2)
    with col1:
        session_count = st.number_input("セッション回数", min_value=1, value=next_session)
        session_date = st.date_input("セッション日", value=date.today())
        next_session_date = st.date_input("次回予定日", value=None)
    with col2:
        _coach_default = selected_ticket["coach_name"] if selected_ticket.get("coach_name") in COACH_LIST else (COACH_LIST[0] if COACH_LIST else None)
        coach_name = st.selectbox("コーチ", COACH_LIST, index=COACH_LIST.index(_coach_default) if _coach_default in COACH_LIST else 0)
        note = st.text_area("メモ（セッション内容・気づきなど）", height=150)

    submitted = st.form_submit_button("追加")

if submitted:
    insert_record("coaching_logs", {
        "id": str(uuid.uuid4()),
        "ticket_id": selected_ticket["id"],
        "user_id": selected_member["id"],
        "name": selected_member["display_name"],
        "session_count": session_count,
        "term_count": selected_ticket["term_count"],
        "session_date": session_date.isoformat(),
        "next_session_date": str(next_session_date) if next_session_date else None,
        "coach_name": coach_name or None,
        "note": note or None,
        "log_type": LOG_TYPE_SESSION,
        "created_at": str(date.today()),
    })
    st.session_state["_toast"] = f"✓ 第{session_count}回セッション記録を追加しました"
    st.rerun()
