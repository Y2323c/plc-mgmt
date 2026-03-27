import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
from datetime import date
import streamlit as st
from utils.supabase_client import get_client
from utils.chatwork import send_message
from utils.secrets import get_secret
from utils.constants import M_STATUS_CAT_COACH, LOG_TYPE_SESSION, LOG_TYPE_MEMO, DATE_FMT_YMD, COACHING_COMPLETION_ROOM_ID

COACHING_CW_TOKEN = get_secret("CHATWORK_COACHING_API_TOKEN")

st.title("コーチング入力")
st.page_link("pages/12_コーチング進捗.py", label="📈 進捗確認ページへ", icon=None)

# トースト表示（保存・送信完了メッセージ）
if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"), icon="✅")
if st.session_state.pop("_ticket_completed", False):
    st.success("🎉 全セッションが完了しました。チケットを終了し、完了通知を送信しました。")

sb = get_client()

# --- コーチ一覧取得（room_id も取得）---
_coaches_raw   = sb.table("m_status").select("label, room_id").eq("category", M_STATUS_CAT_COACH).order("code").execute().data
COACH_LIST     = [c["label"] for c in _coaches_raw]
coach_room_ids = {c["label"]: c.get("room_id") for c in _coaches_raw}

# --- コーチ選択（URLパラメータ対応）---
param_coach    = st.query_params.get("coach")
_coach_default = param_coach if param_coach in COACH_LIST else (COACH_LIST[0] if COACH_LIST else None)

coach_name = st.selectbox(
    "コーチを選択してください",
    COACH_LIST,
    index=COACH_LIST.index(_coach_default) if _coach_default in COACH_LIST else 0,
)

if not coach_name:
    st.stop()

# --- Chatwork通知セクション（セッション保存後に出現）---
if "_notify" in st.session_state:
    n = st.session_state["_notify"]
    next_label = n["next_date"] or "未定"
    base_msg   = f"コーチング完了報告：{n['member_name']} 様\n次回予定：{next_label}\nお疲れさまでした！"

    st.divider()
    st.subheader("📨 Chatworkへの通知")
    st.info("必ず送信してください。内容を確認し、必要に応じて受講生へのメッセージを追記して送信してください。")

    full_msg = st.text_area(
        "メッセージ内容（確認・編集できます）",
        value=base_msg,
        height=160,
        key="notify_msg",
    )

    col_send, col_skip = st.columns([1, 1])
    with col_send:
        if st.button("📨 Chatworkに送信", type="primary"):
            room_id = n.get("room_id")
            if room_id:
                send_message(room_id, full_msg, token=COACHING_CW_TOKEN or None)
                st.session_state["_toast"] = "Chatworkに送信しました"
            else:
                st.warning(f"{n.get('coach_name', '')} のroom_idが未設定です。Supabaseのm_statusで設定してください。")
            del st.session_state["_notify"]
            st.rerun()
    with col_skip:
        if st.button("スキップ"):
            del st.session_state["_notify"]
            st.rerun()
    st.divider()

# --- 担当メンバー一覧（選択コーチの is_active=1 チケット保有者）---
tickets = (
    sb.table("coaching_tickets")
    .select("id, user_id, term_count, coaching_type, max_sessions, name")
    .eq("coach_name", coach_name)
    .eq("is_active", 1)
    .execute()
    .data
)

if not tickets:
    st.warning(f"{coach_name} さんが担当している有効なチケットが見つかりません。")
    st.stop()

uid_to_ticket  = {t["user_id"]: t for t in tickets}
user_ids       = list(uid_to_ticket.keys())

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
selected_name = st.selectbox("担当メンバーを選択してください（有効なチケットがあるメンバーのみ表示）", member_options)
selected_uid  = next((uid for uid, name in uid_to_name.items() if name == selected_name), None)

if not selected_uid:
    st.stop()

selected_ticket = uid_to_ticket[selected_uid]

logs = (
    sb.table("coaching_logs")
    .select("id, log_type, session_count, session_date, coach_name, note")
    .eq("ticket_id", selected_ticket["id"])
    .order("session_date")
    .execute()
    .data
)
session_count_total = sum(1 for l in logs if l.get("log_type") == LOG_TYPE_SESSION)
next_session        = session_count_total + 1
max_sessions        = selected_ticket.get("max_sessions") or 0
last_session_date   = next(
    (l["session_date"] for l in reversed(logs) if l.get("log_type") == LOG_TYPE_SESSION), None
)

# 上限チェック
if max_sessions > 0 and session_count_total >= max_sessions:
    st.warning(f"このチケットの全セッション（{max_sessions}回）が完了しています。セッションを追加できません。")
    st.stop()

# サマリー
st.divider()
_col1, _col2, _col3 = st.columns(3)
_col1.metric("セッション回数", f"{session_count_total} / {max_sessions}" if max_sessions else str(session_count_total))
_col2.metric("残り回数", (max_sessions - session_count_total) if max_sessions else "—")
_col3.metric("最終セッション日", last_session_date or "—")
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
            session_date      = st.date_input("セッション日", value=date.today())
            next_session_date = st.date_input("次回予定日（任意）", value=None)
        with col2:
            note = st.text_area("メモ（セッション内容・気づきなど）", height=150)
        submitted_session = st.form_submit_button("保存", type="primary")

    if submitted_session:
        sb.table("coaching_logs").insert({
            "id":                str(uuid.uuid4()),
            "ticket_id":         selected_ticket["id"],
            "user_id":           selected_uid,
            "name":              selected_name,
            "log_type":          LOG_TYPE_SESSION,
            "session_count":     next_session,
            "term_count":        selected_ticket["term_count"],
            "session_date":      session_date.strftime(DATE_FMT_YMD),
            "next_session_date": next_session_date.strftime(DATE_FMT_YMD) if next_session_date else None,
            "coach_name":        coach_name,
            "note":              note or None,
            "created_at":        date.today().strftime(DATE_FMT_YMD),
        }).execute()
        # 完了チェック
        if max_sessions > 0 and next_session >= max_sessions:
            sb.rpc("complete_coaching_ticket", {"p_ticket_id": selected_ticket["id"]}).execute()
            completion_msg = (
                f"{selected_name}様の{selected_ticket.get('coaching_type', '')} {max_sessions}回"
                f"（担当：{coach_name}）が全セッションを完了しました"
            )
            send_message(COACHING_COMPLETION_ROOM_ID, completion_msg, token=COACHING_CW_TOKEN or None)
            st.session_state["_ticket_completed"] = True

        st.session_state["_toast"]  = "保存しました"
        st.session_state["_notify"] = {
            "member_name": selected_name,
            "coach_name":  coach_name,
            "next_date":   next_session_date.strftime(DATE_FMT_YMD) if next_session_date else None,
            "room_id":     coach_room_ids.get(coach_name),
        }
        st.rerun()

# =====================
# メモタブ
# =====================
with tab_memo:
    st.subheader(f"{selected_name} — メモ")

    with st.form("memo_form"):
        memo_date = st.date_input("日付", value=date.today())
        memo_note = st.text_area("メモ（気づき・観察・準備など）", height=150)
        submitted_memo = st.form_submit_button("保存", type="primary")

    if submitted_memo:
        if not memo_note:
            st.warning("メモを入力してください")
        else:
            sb.table("coaching_logs").insert({
                "id":                str(uuid.uuid4()),
                "ticket_id":         selected_ticket["id"],
                "user_id":           selected_uid,
                "name":              selected_name,
                "log_type":          LOG_TYPE_MEMO,
                "session_count":     None,
                "term_count":        selected_ticket["term_count"],
                "session_date":      memo_date.strftime(DATE_FMT_YMD),
                "next_session_date": None,
                "coach_name":        coach_name,
                "note":              memo_note,
                "created_at":        date.today().strftime(DATE_FMT_YMD),
            }).execute()
            st.session_state["_toast"] = "メモを保存しました"
            st.rerun()
