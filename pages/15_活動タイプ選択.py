import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.supabase_client import get_members, update_record
from utils.style import apply_style

apply_style()

# ── グループチャット URL ──────────────────────────────────────────────────
GROUP_URLS = {
    "プロデューサー":     "https://www.chatwork.com/g/n9zo0vnwsvfh81",
    "コンテンツホルダー": "https://www.chatwork.com/g/kb7g4cp4itou73",
}

# ── 送信後のサンキューページ ─────────────────────────────────────────────
if st.session_state.get("activity_submitted"):
    selected_type = st.session_state["activity_selected_type"]
    selected_name = st.session_state["activity_selected_name"]
    url = GROUP_URLS[selected_type]

    st.title("ありがとうございました！")
    st.success(f"**{selected_name}** さんの活動タイプを **{selected_type}** として登録しました。")
    st.divider()
    st.markdown("### 次のステップ")
    st.markdown("以下のリンクからグループチャットに参加申請をしてください。")
    st.link_button(
        f"{selected_type}のグループチャットに参加申請する",
        url,
        type="primary",
        use_container_width=True,
    )
    st.caption("参加申請後、承認されるとチャットが利用できるようになります。")

    st.write("")
    if st.button("別の方の登録をする", use_container_width=True):
        st.session_state["activity_submitted"] = False
        st.rerun()
    st.stop()

# ── フォーム ─────────────────────────────────────────────────────────────
st.title("活動タイプ選択")
st.caption("プロデューサーまたはコンテンツホルダーを選択して送信してください。その後、グループチャットへの参加申請を行ってください。")
st.write("")

members = get_members(active_only=True)
member_options = {m["display_name"]: m["id"] for m in members}

with st.form("activity_type_form"):
    selected_name = st.selectbox(
        "お名前",
        options=list(member_options.keys()),
        index=None,
        placeholder="名前を入力して検索...",
    )
    st.write("")
    selected_type = st.radio(
        "活動タイプ",
        options=["プロデューサー", "コンテンツホルダー"],
        horizontal=True,
    )
    st.write("")
    submitted = st.form_submit_button("登録する", type="primary", use_container_width=True)

if submitted:
    if not selected_name:
        st.error("お名前を選択してください。")
    else:
        user_id = member_options[selected_name]
        update_record("users_master", {"id": user_id}, {"activity_type": selected_type})
        st.session_state["activity_submitted"] = True
        st.session_state["activity_selected_type"] = selected_type
        st.session_state["activity_selected_name"] = selected_name
        st.rerun()
