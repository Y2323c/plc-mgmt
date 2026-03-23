import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.supabase_client import get_client, get_members, get_events
from utils.ui_helpers import event_selectbox
from utils.constants import STATUS_LABELS, PUBLIC_APP_BASE_URL
from utils.chatwork import get_all_dm_room_ids, send_message

st.title("出欠アンケート配信")

sb = get_client()

# ================================================
# イベント選択
# ================================================
events = get_events()
if not events:
    st.warning("イベントがありません。先に「イベント管理」でイベントを作成してください。")
    st.stop()

selected_event = event_selectbox(events, key="dist_event")
if selected_event is None:
    st.stop()
event_id = selected_event["id"]
event_label = f"{selected_event['category']} {selected_event['label'] or ''} {selected_event['event_date'] or ''}".strip()

st.divider()

# ================================================
# 送付先リスト（在籍のみ: management_status=1）
# ================================================
members = [m for m in get_members(active_only=False) if m.get("management_status") == 1]

st.subheader(f"送付先リスト（在籍 {len(members)}名）")
st.caption("送付する会員にチェックを入れてください。デフォルトは全員選択です。")

search_member = st.text_input("名前で絞り込み", placeholder="名前の一部を入力…", label_visibility="collapsed")

col_check, col_all, col_none = st.columns([6, 1, 1])
with col_all:
    if st.button("全選択"):
        for m in members:
            st.session_state[f"send_{m['id']}"] = True
with col_none:
    if st.button("全解除"):
        for m in members:
            st.session_state[f"send_{m['id']}"] = False

for m in members:
    key = f"send_{m['id']}"
    if key not in st.session_state:
        st.session_state[key] = True

# 既回答者を確認
existing_logs = (
    sb.table("event_logs")
    .select("user_id, status")
    .eq("event_id", event_id)
    .execute()
    .data
)
answered = {r["user_id"]: STATUS_LABELS.get(r["status"], "") for r in existing_logs}

cols = st.columns([0.5, 3, 2, 2])
cols[0].markdown("**送付**")
cols[1].markdown("**氏名**")
cols[2].markdown("**回答状況**")
cols[3].markdown("**Chatwork**")

displayed_members = [m for m in members if search_member.lower() in m["display_name"].lower()] if search_member else members
for m in displayed_members:
    uid = m["id"]
    cols = st.columns([0.5, 3, 2, 2])
    checked = cols[0].checkbox("", key=f"send_{uid}", label_visibility="collapsed")
    status_text = answered.get(uid, "")
    cols[1].write(m["display_name"])
    cols[2].markdown(f"✅ {status_text}" if status_text else "—")
    cols[3].markdown("✓" if m.get("cw_account") else "❌ 未設定")

selected_members = [m for m in members if st.session_state.get(f"send_{m['id']}", True)]
no_cw = [m for m in selected_members if not m.get("cw_account")]
st.caption(f"選択中: {len(selected_members)}名　うちChatwork未設定: {len(no_cw)}名")

st.divider()

# ================================================
# 配信設定
# ================================================
st.subheader("配信設定")

base_url = st.text_input(
    "公開アプリのベースURL",
    value=PUBLIC_APP_BASE_URL,
)

# チェックインURL（当日担当者に共有）
checkin_url = f"{base_url.rstrip('/')}/checkin?event_id={event_id}"
st.text_input(
    "チェックインURL（当日担当者に共有）",
    value=checkin_url,
    help="このURLを当日のチェックイン担当者に送ってください。開くとイベントが自動選択された状態で表示されます。",
)

DEFAULT_TEMPLATE = """[name]さん、こんにちは。

以下のURLから出欠アンケートにご回答ください。

[url]"""

message_template = st.text_area(
    "メッセージテンプレート（[name] → 氏名、[url] → 個別URLに置換されます）",
    value=DEFAULT_TEMPLATE,
    height=160,
)

st.divider()

# ================================================
# 送信
# ================================================
col_url, col_cw = st.columns(2)

# --- URLリスト生成（コピー用）---
with col_url:
    if st.button("URLリストを生成", type="secondary", disabled=(len(selected_members) == 0)):
        lines = []
        for m in selected_members:
            url = f"{base_url.rstrip('/')}/?event_id={event_id}&user_id={m['id']}"
            lines.append(f"{m['display_name']}\n{url}")
        st.text_area(
            "コピーしてChatworkなどに貼り付けてください",
            value="\n\n".join(lines),
            height=300,
        )

# --- Chatwork 一斉送信 ---
with col_cw:
    cw_targets = [m for m in selected_members if m.get("cw_account")]
    if st.button(
        f"Chatwork で送信（{len(cw_targets)}名）",
        type="primary",
        disabled=(len(cw_targets) == 0),
    ):
        progress = st.progress(0, text="DMルームを取得中…")
        try:
            dm_map = get_all_dm_room_ids()
        except Exception as e:
            st.error(f"Chatwork APIエラー: {e}")
            st.stop()

        sent, failed, no_room = [], [], []
        total = len(cw_targets)

        for i, m in enumerate(cw_targets):
            progress.progress((i + 1) / total, text=f"送信中… {m['display_name']} ({i+1}/{total})")
            url = f"{base_url.rstrip('/')}/?event_id={event_id}&user_id={m['id']}"
            body = message_template.replace("[name]", m["display_name"]).replace("[url]", url)
            room_id = dm_map.get(str(m["cw_account"]))

            if not room_id:
                no_room.append(m["display_name"])
                continue

            ok = send_message(room_id, body)
            if ok:
                sent.append(m["display_name"])
                sb.table("message_logs").insert({
                    "user_id": m["id"],
                    "message_body": body,
                    "channel": "chatwork",
                    "status": "sent",
                    "note": f"event:{event_label} room:{room_id}",
                }).execute()
            else:
                failed.append(m["display_name"])

        progress.empty()
        st.success(f"✅ 送信完了：{len(sent)}名")
        if failed:
            st.warning(f"⚠️ 送信失敗：{len(failed)}名 — {', '.join(failed)}")
        if no_room:
            st.warning(f"⚠️ DMルームが見つからず未送信：{len(no_room)}名 — {', '.join(no_room)}")

st.divider()

# ================================================
# 送信履歴
# ================================================
st.subheader("送信履歴")
logs = (
    sb.table("message_logs")
    .select("sent_at, user_id, status, note, message_body")
    .eq("channel", "chatwork")
    .order("sent_at", desc=True)
    .limit(50)
    .execute()
    .data
)

uid_to_name = {m["id"]: m["display_name"] for m in members}

if logs:
    df = pd.DataFrame([{
        "送信日時": l.get("sent_at", "")[:16].replace("T", " "),
        "宛先": uid_to_name.get(l.get("user_id", ""), "—"),
        "ステータス": l.get("status", ""),
        "メモ": l.get("note", ""),
    } for l in logs])
    st.dataframe(df, use_container_width=True)
else:
    st.info("送信履歴はまだありません")
