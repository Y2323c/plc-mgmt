import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.supabase_client import get_client, get_members, get_events, upsert_event_log
from utils.ui_helpers import event_selectbox

st.title("出席管理")

sb = get_client()

# --- URLパラメータ取得 ---
param_event_id = st.query_params.get("event_id")

# --- イベント選択（URLパラメータ優先、なければセレクトボックス） ---
events = get_events()
if not events:
    st.warning("イベントがありません。先に「イベント管理」でイベントを作成してください。")
    st.stop()

event_id_to_event = {e["id"]: e for e in events}

if param_event_id and param_event_id in event_id_to_event:
    selected_event = event_id_to_event[param_event_id]
else:
    selected_event = event_selectbox(events, key="checkin_event")
    if selected_event is None:
        st.info("イベントを選択してください")
        st.stop()

event_title = f"{selected_event['category']} {selected_event['label'] or ''} {selected_event['event_date'] or ''}".strip()

# --- 担当者名 ---
st.subheader(f"{event_title} — チェックイン（当日）")
checker_name = st.text_input("担当者名", placeholder="例: 山田太郎", key="checker_name")
if not checker_name:
    st.info("担当者名を入力するとチェックインできます")
    st.stop()

st.divider()

# --- データ取得 ---
members = get_members(active_only=True)
all_logs = (
    sb.table("event_logs")
    .select("user_id, status, checked_in_by, note")
    .eq("event_id", selected_event["id"])
    .execute()
    .data
)
log_by_uid = {r["user_id"]: r for r in all_logs}

# 会員を分類（チェックイン済みも元のセクションに残す）
attending   = [m for m in members if log_by_uid.get(m["id"], {}).get("status") in (3, 1)]
absent      = [m for m in members if log_by_uid.get(m["id"], {}).get("status") in (4, 2)]
no_response = [m for m in members if m["id"] not in log_by_uid]


def do_checkin(member, status_code):
    upsert_event_log(
        event_id=selected_event["id"],
        user_id=member["id"],
        display_name=member["display_name"],
        event_title=event_title,
        category=selected_event["category"],
        status=status_code,
        checked_in_by=checker_name,
    )
    st.rerun()


def render_member_row(m, default_status_code):
    """スマホ対応レイアウト: 名前→ボタン2列"""
    uid = m["id"]
    log = log_by_uid.get(uid, {})
    current_status = log.get("status", 0)
    note = log.get("note") or ""
    by   = log.get("checked_in_by") or ""

    # 名前 + 備考
    note_text = f"　📝 {note}" if note else ""
    by_text   = f"　（{by}）" if by else ""
    st.markdown(f"**{m['display_name']}**{by_text}{note_text}")

    # ボタン（2等分で押しやすく）
    col1, col2 = st.columns(2)

    if current_status == 1:
        with col1:
            st.success("✅ 出席確定")
        with col2:
            if st.button("取消", key=f"undo_{uid}", use_container_width=True):
                do_checkin(m, 3)   # 参加予定に戻す

    elif current_status == 2:
        with col1:
            st.error("❌ 欠席確定")
        with col2:
            if st.button("取消", key=f"undo_{uid}", use_container_width=True):
                do_checkin(m, 4)   # 欠席予定に戻す

    else:
        with col1:
            if st.button("✅ 出席", key=f"in_{uid}", type="primary", use_container_width=True):
                do_checkin(m, 1)
        with col2:
            if st.button("❌ 欠席", key=f"out_{uid}", use_container_width=True):
                do_checkin(m, 2)

    st.divider()


# --- 確定済みサマリー ---
attend_count = sum(1 for m in members if log_by_uid.get(m["id"], {}).get("status") == 1)
absent_count  = sum(1 for m in members if log_by_uid.get(m["id"], {}).get("status") == 2)
st.markdown(f"**確定済み：出席 {attend_count}名 ／ 欠席 {absent_count}名**")
st.divider()

# --- 名前フィルター ---
search = st.text_input("名前で絞り込み", placeholder="名前の一部を入力…", label_visibility="collapsed")

def filter_by_name(lst, query):
    if not query:
        return lst
    q = query.lower()
    return [m for m in lst if q in m["display_name"].lower()]

attending_view   = filter_by_name(attending,   search)
absent_view      = filter_by_name(absent,      search)
no_response_view = filter_by_name(no_response, search)

# --- 参加予定 ---
if attending_view:
    st.markdown(f"**── 参加予定（{len(attending_view)}名）──**")
    for m in attending_view:
        render_member_row(m, 3)

# --- 欠席予定 ---
if absent_view:
    st.markdown(f"**── 欠席予定（{len(absent_view)}名）──**")
    for m in absent_view:
        render_member_row(m, 4)

# --- 未回答（デフォルト折りたたみ・検索時は自動展開） ---
if no_response_view:
    with st.expander(f"未回答（{len(no_response_view)}名）", expanded=bool(search)):
        for m in no_response_view:
            render_member_row(m, None)
