import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.supabase_client import get_client, get_members, get_events, get_event_log, upsert_event_log
from utils.ui_helpers import event_selectbox
from utils.constants import SURVEY_OPTIONS, STATUS_LABELS

sb = get_client()

# ================================================
# URL パラメータ取得
# 将来: ?event_id=xxx&user_id=yyy でアクセス
# ================================================
params = st.query_params
param_event_id = params.get("event_id")
param_user_id = params.get("user_id")


# ================================================
# イベント特定
# ================================================
events = get_events()
if not events:
    st.error("現在回答できるイベントがありません。")
    st.stop()

event_id_to_event = {e["id"]: e for e in events}
selected_event = None

if param_event_id and param_event_id in event_id_to_event:
    # URL パラメータでイベント指定済み
    selected_event = event_id_to_event[param_event_id]
else:
    # セレクトボックスで選択
    st.subheader("イベントを選択してください")
    selected_event = event_selectbox(events, key="survey_event")
    if selected_event is None:
        st.stop()

event_label = f"{selected_event['category']} {selected_event['label'] or ''} {selected_event['event_date'] or ''}".strip()

# ================================================
# 会員特定
# ================================================
members = get_members(active_only=True)
uid_to_member = {m["id"]: m for m in members}
selected_member = None

if param_user_id and param_user_id in uid_to_member:
    # URL パラメータで会員指定済み
    selected_member = uid_to_member[param_user_id]
else:
    # セレクトボックスで選択
    name_to_member = {m["display_name"]: m for m in members}
    selected_name = st.selectbox(
        "お名前を選択してください",
        list(name_to_member.keys()),
        index=None,
        placeholder="お名前を入れてください",
    )
    if selected_name is None:
        st.stop()
    selected_member = name_to_member[selected_name]

# ================================================
# アンケート画面
# ================================================
st.title("出席アンケート")
st.markdown(f"### {event_label}")
st.markdown(f"**{selected_member['display_name']}** さんの回答")
st.divider()

# 既存回答を取得
existing = get_event_log(selected_event["id"], selected_member["id"])
current_status = existing["status"] if existing else None

if current_status in STATUS_LABELS:
    st.info(f"現在の回答: **{STATUS_LABELS[current_status]}**")

current_label = STATUS_LABELS.get(current_status, "")
answer = st.radio(
    "ご参加の予定を教えてください",
    list(SURVEY_OPTIONS.keys()),
    index=list(SURVEY_OPTIONS.keys()).index(current_label)
          if current_label in SURVEY_OPTIONS else None,
    horizontal=True,
)

note = st.text_area(
    "備考（任意）",
    value=existing.get("note") or "" if existing else "",
    placeholder="欠席理由・遅刻・早退など、連絡事項があればご記入ください",
    height=100,
)

if st.button("回答を送信", type="primary", disabled=(answer is None)):
    upsert_event_log(
        event_id=selected_event["id"],
        user_id=selected_member["id"],
        display_name=selected_member["display_name"],
        event_title=event_label,
        category=selected_event["category"],
        status=SURVEY_OPTIONS[answer],
        note=note or None,
    )
    st.success(f"✓ **{answer}** で回答しました")
    st.balloons()
