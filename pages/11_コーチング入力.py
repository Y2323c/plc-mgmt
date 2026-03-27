import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
from datetime import date
import streamlit as st
from utils.supabase_client import get_client
from utils.constants import M_STATUS_CAT_COACH, LOG_TYPE_SESSION, LOG_TYPE_MEMO, DATE_FMT_YMD

st.title("コーチング記録")

sb = get_client()

# --- コーチ一覧取得 ---
_coaches_raw = sb.table("m_status").select("label").eq("category", M_STATUS_CAT_COACH).order("code").execute().data
COACH_LIST = [c["label"] for c in _coaches_raw if c["label"] != ".準備中"]

# --- コーチ選択（URLパラメータ対応）---
param_coach = st.query_params.get("coach")
_coach_default = param_coach if param_coach in COACH_LIST else (COACH_LIST[0] if COACH_LIST else None)

coach_name = st.selectbox(
    "コーチを選択してください",
    COACH_LIST,
    index=COACH_LIST.index(_coach_default) if _coach_default in COACH_LIST else 0,
)

if not coach_name:
    st.stop()

# --- 担当メンバー一覧（選択コーチの is_active=1 チケット保有者）---
tickets = (
    sb.table("coaching_tickets")
    .select("id, user_id, term_count, coaching_type")
    .eq("coach_name", coach_name)
    .eq("is_active", 1)
    .execute()
    .data
)

if not tickets:
    st.warning(f"{coach_name} さんが担当している有効なチケットが見つかりません。")
    st.stop()

# user_id → チケット情報のマッピング
uid_to_ticket = {t["user_id"]: t for t in tickets}
user_ids = list(uid_to_ticket.keys())

# メンバーの表示名を取得
members_raw = (
    sb.table("name_mappings")
    .select("user_id, clean_name")
    .in_("user_id", user_ids)
    .execute()
    .data
)
uid_to_name = {m["user_id"]: m["clean_name"] for m in members_raw}

member_options = sorted([uid_to_name.get(uid, uid) for uid in user_ids])

# --- メンバー選択 ---
selected_name = st.selectbox("担当メンバーを選択してください", member_options)
selected_uid = next((uid for uid, name in uid_to_name.items() if name == selected_name), None)

if not selected_uid:
    st.stop()

selected_ticket = uid_to_ticket[selected_uid]

# セッション回数（log_type='session' のみカウント）
logs = (
    sb.table("coaching_logs")
    .select("id, log_type, session_count, session_date, coach_name, note")
    .eq("ticket_id", selected_ticket["id"])
    .order("session_date")
    .execute()
    .data
)
next_session = sum(1 for l in logs if l.get("log_type") == LOG_TYPE_SESSION) + 1

st.divider()

# --- タブ ---
tab_session, tab_memo = st.tabs(["📝 セッション記録", "💬 メモ"])

# =====================
# セッション記録タブ
# =====================
with tab_session:
    st.subheader(f"{selected_name} — 第{next_session}回 セッション記録")

    with st.form("session_form"):
        col1, col2 = st.columns(2)
        with col1:
            session_date = st.date_input("セッション日", value=date.today())
            next_session_date = st.date_input("次回予定日（任意）", value=None)
        with col2:
            note = st.text_area("メモ（セッション内容・気づきなど）", height=150)
        submitted_session = st.form_submit_button("送信", type="primary")

    if submitted_session:
        sb.table("coaching_logs").insert({
            "id": str(uuid.uuid4()),
            "ticket_id": selected_ticket["id"],
            "user_id": selected_uid,
            "name": selected_name,
            "log_type": LOG_TYPE_SESSION,
            "session_count": next_session,
            "term_count": selected_ticket["term_count"],
            "session_date": session_date.strftime(DATE_FMT_YMD),
            "next_session_date": next_session_date.strftime(DATE_FMT_YMD) if next_session_date else None,
            "coach_name": coach_name,
            "note": note or None,
            "created_at": date.today().strftime(DATE_FMT_YMD),
        }).execute()
        st.success(f"✓ {selected_name} さんの第{next_session}回セッションを記録しました")
        st.balloons()

# =====================
# メモタブ
# =====================
with tab_memo:
    st.subheader(f"{selected_name} — メモ")

    with st.form("memo_form"):
        memo_date = st.date_input("日付", value=date.today())
        memo_note = st.text_area("メモ（気づき・観察・準備など）", height=150)
        submitted_memo = st.form_submit_button("送信", type="primary")

    if submitted_memo:
        if not memo_note:
            st.warning("メモを入力してください")
        else:
            sb.table("coaching_logs").insert({
                "id": str(uuid.uuid4()),
                "ticket_id": selected_ticket["id"],
                "user_id": selected_uid,
                "name": selected_name,
                "log_type": LOG_TYPE_MEMO,
                "session_count": None,
                "term_count": selected_ticket["term_count"],
                "session_date": memo_date.strftime(DATE_FMT_YMD),
                "next_session_date": None,
                "coach_name": coach_name,
                "note": memo_note,
                "created_at": date.today().strftime(DATE_FMT_YMD),
            }).execute()
            st.success(f"✓ {selected_name} さんのメモを保存しました")
