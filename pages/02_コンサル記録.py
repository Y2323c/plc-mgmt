import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import date
from utils.supabase_client import get_client, insert_record
from utils.ui_helpers import member_selectbox
from utils.constants import CONSULT_TYPES, CAT_CONSULT, ST_ATTENDED

st.title("コンサル記録")

if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"), icon="✅")

sb = get_client()

# --- サイドバー ---
with st.sidebar:
    st.header("会員選択")
    selected_member = member_selectbox(key="member_consult", show_all_key="show_all_consult")
    if selected_member is None:
        st.info("会員を選択してください")
        st.stop()
    st.caption(f"user_id: {selected_member['id']}")

# --- その会員のコンサルログ ---
logs = (
    sb.table("event_logs")
    .select("*")
    .eq("user_id", selected_member["id"])
    .eq("category", CAT_CONSULT)
    .execute()
    .data
)

st.subheader(f"{selected_member['display_name']} のコンサル記録（{len(logs)}件）")

if logs:
    df = pd.DataFrame([{
        "id": l["id"],
        "種別": l.get("consult_type") or "",
        "実施日": l.get("consult_date") or "",
        "メモ": l.get("note") or "",
    } for l in logs])
    st.dataframe(df.drop(columns=["id"]), use_container_width=True)
else:
    st.info("記録がありません")

# --- 追加フォーム ---
st.divider()
st.subheader("コンサルを記録")
with st.form("consult_form"):
    col1, col2 = st.columns(2)
    with col1:
        consult_type = st.selectbox("コンサル種別", CONSULT_TYPES)
        consult_date = st.date_input("実施日", value=date.today())
    with col2:
        note = st.text_area("メモ")
    submitted = st.form_submit_button("追加")

if submitted:
    insert_record("event_logs", {
        "user_id": selected_member["id"],
        "category": CAT_CONSULT,
        "title": None,
        "name": selected_member["display_name"],
        "status": ST_ATTENDED,
        "consult_type": consult_type,
        "consult_date": consult_date.isoformat(),
        "event_id": None,
        "note": note or None,
    })
    st.session_state["_toast"] = f"✓ {consult_type}コンサル（{consult_date}）を記録しました"
    st.rerun()
