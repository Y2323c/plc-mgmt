import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
from datetime import date
import streamlit as st
import pandas as pd
from utils.supabase_client import get_client, insert_record
from utils.ui_helpers import member_selectbox

st.title("コーチング記録")

sb = get_client()

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

ticket_labels = [f"{t['term_count']}期（{t['start_date'] or '日付なし'}）{'✓' if t['is_active'] else ''}" for t in tickets]
ticket_idx = st.selectbox("チケット選択", range(len(tickets)), format_func=lambda i: ticket_labels[i])
selected_ticket = tickets[ticket_idx]

# --- セッション一覧 ---
logs = sb.table("coaching_logs").select("*").eq("ticket_id", selected_ticket["id"]).order("session_count").execute().data

st.subheader(f"{selected_ticket['term_count']}期 セッション記録（{len(logs)}件）")

if logs:
    df = pd.DataFrame([{
        "回": l["session_count"],
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
next_session = len(logs) + 1
st.subheader(f"第{next_session}回 セッション記録を追加")

with st.form("coaching_log_form"):
    col1, col2 = st.columns(2)
    with col1:
        session_count = st.number_input("セッション回数", min_value=1, value=next_session)
        session_date = st.date_input("セッション日", value=date.today())
        next_session_date = st.date_input("次回予定日", value=None)
    with col2:
        coach_name = st.text_input("コーチ名", value=selected_ticket["coach_name"] or "")
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
        "created_at": str(date.today()),
    })
    st.success(f"✓ 第{session_count}回セッション記録を追加しました")
    st.rerun()
