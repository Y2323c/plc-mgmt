import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.supabase_client import get_client, get_next_term_count, insert_record
from utils.ui_helpers import member_selectbox

st.title("コーチングチケット")

sb = get_client()

# --- サイドバー ---
with st.sidebar:
    st.header("会員選択")
    selected_member = member_selectbox(key="member_ticket", show_all_key="show_all_ticket")
    if selected_member is None:
        st.info("会員を選択してください")
        st.stop()

# --- その会員のチケット一覧 ---
tickets = sb.table("coaching_tickets").select("*").eq("user_id", selected_member["id"]).order("term_count").execute().data

st.subheader(f"{selected_member['display_name']} のチケット（{len(tickets)}件）")

if tickets:
    df = pd.DataFrame([{
        "期": t["term_count"],
        "コーチ": t["coach_name"] or "",
        "開始日": t["start_date"] or "",
        "期間（月）": t["duration_months"] or "",
        "有効期限": t["expired_at"] or "",
        "最大セッション": t["max_sessions"] or "",
        "有効": "✓" if t["is_active"] else "",
        "_id": t["id"],
    } for t in tickets])

    # 編集対象の選択
    ticket_options = ["新規追加"] + [f"{t['term_count']}期（{t['start_date'] or '日付なし'}）" for t in tickets]
    edit_choice = st.selectbox("編集するチケット", range(len(ticket_options)), format_func=lambda i: ticket_options[i])
    selected_ticket = None if edit_choice == 0 else tickets[edit_choice - 1]

    st.dataframe(df.drop(columns=["_id"]), use_container_width=True)
else:
    st.info("チケットがありません")
    edit_choice = 0
    selected_ticket = None

# --- フォーム ---
st.divider()
next_term = get_next_term_count(selected_member["id"])
is_new = selected_ticket is None

st.subheader("新規追加" if is_new else f"{selected_ticket['term_count']}期 編集")

with st.form("ticket_form"):
    col1, col2 = st.columns(2)
    with col1:
        term_count = st.number_input(
            "期（term_count）",
            min_value=0, value=int(selected_ticket["term_count"]) if selected_ticket else next_term
        )
        coach_name = st.text_input("コーチ名", value=selected_ticket["coach_name"] or "" if selected_ticket else "")
        try:
            _sd_default = datetime.strptime(selected_ticket["start_date"] or "", "%Y/%m/%d").date() if selected_ticket and selected_ticket.get("start_date") else date.today()
        except ValueError:
            _sd_default = date.today()
        _sd_date = st.date_input("開始日", value=_sd_default)
        start_date = _sd_date.strftime("%Y/%m/%d")
    with col2:
        max_sessions = st.number_input("最大セッション数", min_value=0, value=int(selected_ticket["max_sessions"] or 0) if selected_ticket else 0)
        duration_months = st.number_input("期間（月）", min_value=0, value=int(selected_ticket["duration_months"] or 0) if selected_ticket else 0)
        try:
            _ea_default = datetime.strptime(selected_ticket["expired_at"] or "", "%Y/%m/%d").date() if selected_ticket and selected_ticket.get("expired_at") else date.today()
        except ValueError:
            _ea_default = date.today()
        _ea_date = st.date_input("有効期限", value=_ea_default)
        expired_at = _ea_date.strftime("%Y/%m/%d")
        is_active = st.checkbox("有効（is_active）", value=bool(selected_ticket["is_active"]) if selected_ticket else True)

    submitted = st.form_submit_button("保存")

if submitted:
    data = {
        "user_id": selected_member["id"],
        "name": selected_member["display_name"],
        "term_count": term_count,
        "coach_name": coach_name or None,
        "start_date": start_date or None,
        "max_sessions": max_sessions or None,
        "duration_months": duration_months or None,
        "expired_at": expired_at or None,
        "is_active": 1 if is_active else 0,
    }
    if is_new:
        data["id"] = str(uuid.uuid4())
        insert_record("coaching_tickets", data)
        st.success(f"✓ {term_count}期チケットを追加しました")
    else:
        sb.table("coaching_tickets").update(data).eq("id", selected_ticket["id"]).execute()
        st.success(f"✓ {term_count}期チケットを更新しました")
    st.rerun()
