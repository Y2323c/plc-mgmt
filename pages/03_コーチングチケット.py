import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from utils.supabase_client import get_client, get_next_term_count, insert_record
from utils.ui_helpers import member_selectbox
from utils.constants import DATE_FMT_YMD, M_STATUS_CAT_COACH, M_STATUS_CAT_COACHING_TYPE, COACHING_TYPE_DEFAULTS

st.title("コーチングチケット")

if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"), icon="✅")

sb = get_client()

# --- コーチ一覧取得 ---
_coaches_raw = sb.table("m_status").select("label").eq("category", M_STATUS_CAT_COACH).order("code").execute().data
COACH_LIST = [c["label"] for c in _coaches_raw]

# --- コーチング種別取得 ---
_types_raw = sb.table("m_status").select("label").eq("category", M_STATUS_CAT_COACHING_TYPE).order("code").execute().data
COACHING_TYPE_LIST = [t["label"] for t in _types_raw]

# --- サイドバー ---
with st.sidebar:
    st.header("会員選択")
    selected_member = member_selectbox(key="member_ticket", show_all_key="show_all_ticket")
    if selected_member is None:
        st.info("会員を選択してください")
        st.stop()

# --- その会員のチケット一覧取得 ---
tickets = sb.table("coaching_tickets").select("*").eq("user_id", selected_member["id"]).order("term_count").execute().data

st.subheader(f"{selected_member['display_name']} のチケット（{len(tickets)}件）")

# --- 共通フォーム描画関数 ---
def render_ticket_form(form_key: str, selected_ticket: dict | None, next_term: int):
    """チケット入力フォームを描画して保存処理まで行う"""
    is_new = selected_ticket is None

    # 種別選択（フォーム外 → デフォルト値を動的に反映）
    _type_default = (
        selected_ticket.get("coaching_type")
        if selected_ticket and selected_ticket.get("coaching_type") in COACHING_TYPE_LIST
        else (COACHING_TYPE_LIST[0] if COACHING_TYPE_LIST else None)
    )
    coaching_type = st.segmented_control(
        "コーチング種別",
        COACHING_TYPE_LIST,
        default=_type_default,
        key=f"coaching_type_{form_key}"
    )

    # 種別に応じたデフォルト値
    _type_defaults = COACHING_TYPE_DEFAULTS.get(coaching_type or "", {})
    _def_max = _type_defaults.get("max_sessions", 0)
    _def_dur = _type_defaults.get("duration_months", 0)

    with st.form(form_key):
        col1, col2 = st.columns(2)
        with col1:
            term_count = st.number_input(
                "期（term_count）",
                min_value=0,
                value=int(selected_ticket["term_count"]) if selected_ticket else next_term
            )
            _coach_default = (
                selected_ticket["coach_name"]
                if selected_ticket and selected_ticket.get("coach_name") in COACH_LIST
                else (COACH_LIST[0] if COACH_LIST else None)
            )
            coach_name = st.selectbox(
                "コーチ", COACH_LIST,
                index=COACH_LIST.index(_coach_default) if _coach_default in COACH_LIST else 0
            )
            try:
                _sd_default = (
                    datetime.strptime(selected_ticket["start_date"] or "", DATE_FMT_YMD).date()
                    if selected_ticket and selected_ticket.get("start_date")
                    else date.today()
                )
            except ValueError:
                _sd_default = date.today()
            _sd_date = st.date_input("開始日", value=_sd_default)
            start_date = _sd_date.strftime(DATE_FMT_YMD)
        with col2:
            max_sessions = st.number_input(
                "最大セッション数", min_value=0,
                value=int(selected_ticket["max_sessions"] or 0) if selected_ticket else _def_max
            )
            duration_months = st.number_input(
                "期間（月）", min_value=0,
                value=int(selected_ticket["duration_months"] or 0) if selected_ticket else _def_dur,
                help="期間 > 0 の場合は開始日＋期間で有効期限を自動計算。0 の場合は有効期限なし（2099/12/31）として保存。"
            )
            is_active = st.checkbox(
                "有効（is_active）",
                value=bool(selected_ticket["is_active"]) if selected_ticket else True
            )
            send_reminder = st.checkbox(
                "リマインド送信する",
                value=bool(selected_ticket.get("send_reminder", True)) if selected_ticket else True,
                help="OFFにすると月次レポートには表示されますが、日次リマインドは送信されません（制度変更前の会員など）"
            )

        submitted = st.form_submit_button("保存")

    if submitted:
        # 有効期限の自動計算
        if duration_months and duration_months > 0:
            try:
                _start = datetime.strptime(start_date, DATE_FMT_YMD).date()
                expired_at = (_start + relativedelta(months=duration_months)).strftime(DATE_FMT_YMD)
            except Exception:
                expired_at = "2099/12/31"
        else:
            expired_at = "2099/12/31"

        data = {
            "user_id": selected_member["id"],
            "name": selected_member["display_name"],
            "coaching_type": coaching_type or None,
            "term_count": term_count,
            "coach_name": coach_name or None,
            "start_date": start_date or None,
            "max_sessions": max_sessions or None,
            "duration_months": duration_months or None,
            "expired_at": expired_at,
            "is_active": 1 if is_active else 0,
            "send_reminder": send_reminder,
        }
        if is_new:
            data["id"] = str(uuid.uuid4())
            insert_record("coaching_tickets", data)
            st.session_state["_toast"] = f"✓ {term_count}期チケットを追加しました"
        else:
            sb.table("coaching_tickets").update(data).eq("id", selected_ticket["id"]).execute()
            st.session_state["_toast"] = f"✓ {term_count}期チケットを更新しました"
        st.rerun()

# --- タブ ---
tab_new, tab_edit = st.tabs(["➕ 新規追加", "✏️ 既存チケットを編集"])

next_term = get_next_term_count(selected_member["id"])

# =====================
# 新規追加タブ
# =====================
with tab_new:
    render_ticket_form("form_new", None, next_term)

# =====================
# 既存チケットを編集タブ
# =====================
with tab_edit:
    if not tickets:
        st.info("チケットがありません。まず「新規追加」タブから登録してください。")
    else:
        # チケット一覧テーブル
        df = pd.DataFrame([{
            "期": t["term_count"],
            "種別": t.get("coaching_type") or "",
            "コーチ": t["coach_name"] or "",
            "開始日": t["start_date"] or "",
            "期間（月）": t["duration_months"] or "",
            "有効期限": t["expired_at"] or "",
            "最大セッション": t["max_sessions"] or "",
            "有効": "✓" if t["is_active"] else "",
        } for t in tickets])
        st.dataframe(df, use_container_width=True)

        # チケット選択
        ticket_labels = [
            f"{t['term_count']}期｜{t.get('coaching_type') or '種別なし'}｜{t.get('coach_name') or 'コーチ未定'}{'　✓' if t['is_active'] else '　終了'}"
            for t in tickets
        ]
        ticket_idx = st.selectbox("編集するチケットを選択", range(len(tickets)), format_func=lambda i: ticket_labels[i])
        selected_ticket = tickets[ticket_idx]

        st.warning(f"✏️ {selected_ticket['term_count']}期（{selected_ticket.get('coaching_type') or '種別なし'} / {selected_ticket.get('coach_name') or 'コーチ未定'}）を編集中")
        st.divider()

        render_ticket_form("form_edit", selected_ticket, next_term)
