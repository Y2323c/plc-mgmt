import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
from datetime import date
import streamlit as st
import pandas as pd
from utils.supabase_client import get_client, insert_record, get_coaches
from utils.ui_helpers import member_selectbox
from utils.chatwork import send_message
from utils.secrets import get_secret
from utils.constants import LOG_TYPE_SESSION, LOG_TYPE_MEMO, DATE_FMT_YMD, COACHING_COMPLETION_ROOM_ID

COACHING_CW_TOKEN = get_secret("CHATWORK_COACHING_API_TOKEN")

st.title("コーチング記録（管理）")

if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"), icon="✅")
if st.session_state.pop("_ticket_completed", False):
    st.success("🎉 全セッションが完了しました。チケットを終了し、完了通知を送信しました。")

sb = get_client()

# --- コーチ一覧取得 ---
COACH_LIST = [c["label"] for c in get_coaches()]

# --- サイドバー ---
with st.sidebar:
    st.header("会員選択")
    selected_member = member_selectbox(key="member_coaching", show_all_key="show_all_coaching")
    if selected_member is None:
        st.info("会員を選択してください")
        st.stop()

# --- チケット選択（有効のみ）---
tickets = (
    sb.table("coaching_tickets")
    .select("*")
    .eq("user_id", selected_member["id"])
    .eq("is_active", 1)
    .order("term_count")
    .execute()
    .data
)

st.subheader(f"{selected_member['display_name']}")

if not tickets:
    st.warning("有効なチケットがありません。先にコーチングチケットを登録してください。")
    st.stop()

ticket_labels = [f"{t['term_count']}期 — {t.get('coaching_type') or '種別なし'}（{t.get('coach_name') or 'コーチ未定'}）" for t in tickets]
ticket_idx = st.selectbox("チケット選択", range(len(tickets)), format_func=lambda i: ticket_labels[i])
selected_ticket = tickets[ticket_idx]

# --- 記録一覧 ---
logs = (
    sb.table("coaching_logs")
    .select("*")
    .eq("ticket_id", selected_ticket["id"])
    .order("session_date")
    .execute()
    .data
)

session_count_total = sum(1 for l in logs if l.get("log_type") == LOG_TYPE_SESSION)
next_session = session_count_total + 1
max_sessions = selected_ticket.get("max_sessions") or 0

st.subheader(f"{selected_ticket['term_count']}期 記録（セッション{session_count_total}回 / 全{len(logs)}件）")

if max_sessions > 0 and session_count_total >= max_sessions:
    st.warning(f"このチケットの全セッション（{max_sessions}回）が完了しています。セッションを追加できません。")

if logs:
    df = pd.DataFrame([{
        "種別":       "セッション" if l.get("log_type") == LOG_TYPE_SESSION else "メモ",
        "回":         l["session_count"] or "",
        "セッション日": l["session_date"] or "",
        "次回予定":   l["next_session_date"] or "",
        "コーチ":     l["coach_name"] or "",
        "メモ":       (l["note"] or "")[:50] + ("…" if len(l["note"] or "") > 50 else ""),
    } for l in logs])
    st.dataframe(df, use_container_width=True)
else:
    st.info("記録がありません")

# --- フォーム（タブ）---
st.divider()

tab_session, tab_memo, tab_edit = st.tabs(["📝 セッション記録を追加", "💬 メモを追加", "✏️ 記録を編集・削除"])

# ── セッション ──
with tab_session:
    if max_sessions > 0 and session_count_total >= max_sessions:
        st.info("セッション上限に達しているため追加できません。チケットを確認してください。")
    else:
        st.subheader(f"第{next_session}回 セッション記録")
        with st.form("session_form"):
            col1, col2 = st.columns(2)
            with col1:
                session_date = st.date_input("セッション日", value=date.today())
                next_session_date = st.date_input("次回予定日（任意）", value=None)
            with col2:
                _coach_default = selected_ticket["coach_name"] if selected_ticket.get("coach_name") in COACH_LIST else (COACH_LIST[0] if COACH_LIST else None)
                coach_name = st.selectbox("コーチ", COACH_LIST, index=COACH_LIST.index(_coach_default) if _coach_default in COACH_LIST else 0)
                note = st.text_area("メモ（セッション内容・気づきなど）", height=150)
            submitted_session = st.form_submit_button("保存", type="primary")

        if submitted_session:
            try:
                insert_record("coaching_logs", {
                    "id":                str(uuid.uuid4()),
                    "ticket_id":         selected_ticket["id"],
                    "user_id":           selected_member["id"],
                    "name":              selected_member["display_name"],
                    "log_type":          LOG_TYPE_SESSION,
                    "session_count":     next_session,
                    "term_count":        selected_ticket["term_count"],
                    "session_date":      session_date.strftime(DATE_FMT_YMD),
                    "next_session_date": next_session_date.strftime(DATE_FMT_YMD) if next_session_date else None,
                    "coach_name":        coach_name or None,
                    "note":              note or None,
                    "created_at":        date.today().strftime(DATE_FMT_YMD),
                })
                if max_sessions > 0 and next_session >= max_sessions:
                    get_client().table("coaching_tickets").update({"is_active": 0}).eq("id", selected_ticket["id"]).execute()
                    completion_msg = (
                        f"{selected_member['display_name']}様の{selected_ticket.get('coaching_type', '')} {max_sessions}回"
                        f"（担当：{coach_name}）が全セッションを完了しました"
                    )
                    send_message(COACHING_COMPLETION_ROOM_ID, completion_msg, token=COACHING_CW_TOKEN or None)
                    st.session_state["_ticket_completed"] = True
                st.session_state["_toast"] = f"✓ 第{next_session}回セッション記録を保存しました"
                st.rerun()
            except Exception as e:
                st.error(f"保存に失敗しました: {e}")

# ── メモ ──
with tab_memo:
    st.subheader("メモを追加")
    with st.form("memo_form"):
        memo_date = st.date_input("日付", value=date.today())
        memo_note = st.text_area("メモ（気づき・観察・準備など）", height=150)
        submitted_memo = st.form_submit_button("保存", type="primary")

    if submitted_memo:
        if not memo_note:
            st.warning("メモを入力してください")
        else:
            insert_record("coaching_logs", {
                "id":                str(uuid.uuid4()),
                "ticket_id":         selected_ticket["id"],
                "user_id":           selected_member["id"],
                "name":              selected_member["display_name"],
                "log_type":          LOG_TYPE_MEMO,
                "session_count":     None,
                "term_count":        selected_ticket["term_count"],
                "session_date":      memo_date.strftime(DATE_FMT_YMD),
                "next_session_date": None,
                "coach_name":        selected_ticket.get("coach_name") or None,
                "note":              memo_note,
                "created_at":        date.today().strftime(DATE_FMT_YMD),
            })
            st.session_state["_toast"] = "✓ メモを保存しました"
            st.rerun()

# ── 編集・削除 ──
with tab_edit:
    if not logs:
        st.info("編集・削除できる記録がありません。")
    else:
        log_labels = [
            f"{'セッション' if l.get('log_type') == LOG_TYPE_SESSION else 'メモ'}"
            f"｜{l.get('session_date') or '日付なし'}"
            + (f"｜第{l['session_count']}回" if l.get("session_count") else "")
            for l in logs
        ]
        edit_idx = st.selectbox("編集するログを選択", range(len(logs)), format_func=lambda i: log_labels[i], key="edit_log_idx")
        target = logs[edit_idx]

        st.divider()

        with st.form("edit_form"):
            _sd = None
            try:
                _sd = date.fromisoformat((target.get("session_date") or "").replace("/", "-"))
            except Exception:
                _sd = date.today()
            _nd = None
            try:
                _nd = date.fromisoformat((target.get("next_session_date") or "").replace("/", "-")) if target.get("next_session_date") else None
            except Exception:
                _nd = None

            ecol1, ecol2 = st.columns(2)
            with ecol1:
                edit_date      = st.date_input("セッション日", value=_sd)
                edit_next_date = st.date_input("次回予定日（任意）", value=_nd)
            with ecol2:
                _ec_default = target.get("coach_name") if target.get("coach_name") in COACH_LIST else (COACH_LIST[0] if COACH_LIST else None)
                edit_coach = st.selectbox("コーチ", COACH_LIST, index=COACH_LIST.index(_ec_default) if _ec_default in COACH_LIST else 0)
                edit_note  = st.text_area("メモ", value=target.get("note") or "", height=150)

            col_save, col_del = st.columns([1, 1])
            with col_save:
                do_save = st.form_submit_button("保存", type="primary")
            with col_del:
                do_delete = st.form_submit_button("削除", type="secondary")

        if do_save:
            sb.table("coaching_logs").update({
                "session_date":      edit_date.strftime(DATE_FMT_YMD),
                "next_session_date": edit_next_date.strftime(DATE_FMT_YMD) if edit_next_date else None,
                "coach_name":        edit_coach or None,
                "note":              edit_note or None,
            }).eq("id", target["id"]).execute()
            st.session_state["_toast"] = "✓ 記録を更新しました"
            st.rerun()

        if do_delete:
            sb.table("coaching_logs").delete().eq("id", target["id"]).execute()
            st.session_state["_toast"] = "✓ 記録を削除しました"
            st.rerun()
