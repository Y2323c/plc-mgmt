import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.supabase_client import get_members
from utils.style import apply_style

apply_style()

st.title("活動タイプ管理")

members = get_members(active_only=True)

# 集計
type_counts: dict[str, int] = {}
unanswered: list[dict] = []
answered:   list[dict] = []

for m in members:
    at = (m.get("activity_type") or "").strip()
    if not at or at == "未定":
        unanswered.append(m)
    else:
        answered.append(m)
        type_counts[at] = type_counts.get(at, 0) + 1

# ── サマリー ──────────────────────────────────────────────────────────────
st.subheader("回答状況")
c1, c2, c3, c4 = st.columns(4)
c1.metric("プロデューサー",     type_counts.get("プロデューサー", 0))
c2.metric("コンテンツホルダー", type_counts.get("コンテンツホルダー", 0))
c3.metric("両方",               type_counts.get("両方", 0))
c4.metric("⚠️ 未回答",          len(unanswered))

st.divider()

# ── 未回答者一覧 ─────────────────────────────────────────────────────────
st.subheader(f"未回答者一覧（{len(unanswered)}名）")
if unanswered:
    df_un = pd.DataFrame([{"名前": m["display_name"]} for m in unanswered])
    st.dataframe(df_un, hide_index=True, use_container_width=True)
else:
    st.success("全員回答済みです ✅")

st.divider()

# ── 回答済み一覧 ─────────────────────────────────────────────────────────
st.subheader(f"回答済み一覧（{len(answered)}名）")
if answered:
    df_an = pd.DataFrame([
        {
            "名前":       m["display_name"],
            "活動タイプ": m.get("activity_type") or "",
        }
        for m in answered
    ])
    st.dataframe(df_an, hide_index=True, use_container_width=True)
