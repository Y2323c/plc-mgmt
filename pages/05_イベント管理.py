import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from datetime import date
from utils.supabase_client import get_client, get_events, insert_record, update_record
from utils.constants import EVENT_CATEGORIES
from utils.ui_helpers import event_selectbox, show_dataframe

st.title("イベント管理（WS / チーム）")

if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"), icon="✅")

sb = get_client()

# --- イベント一覧 ---
events = get_events()

st.subheader(f"イベント一覧（{len(events)}件）")

show_dataframe(events, {"カテゴリ": "category", "日付": "event_date", "ラベル": "label", "メモ": "note"})

st.divider()

# --- 操作選択 ---
col_new, col_edit = st.columns(2)

# ====== 新規追加 ======
with col_new:
    st.subheader("新規イベント追加")
    with st.form("add_event_form"):
        category = st.selectbox("カテゴリ", EVENT_CATEGORIES, key="add_cat")
        event_date = st.date_input("日付", value=date.today(), key="add_date")
        label = st.text_input("ラベル（例: チーム⑫、午前の部）", key="add_label")
        note = st.text_area("メモ", key="add_note")
        submitted_add = st.form_submit_button("追加")

    if submitted_add:
        if not label:
            st.error("ラベルを入力してください")
        else:
            insert_record("events", {
                "category": category,
                "event_date": event_date.isoformat(),
                "label": label,
                "note": note or None,
            })
            st.session_state["_toast"] = f"✓ {category} {label}（{event_date}）を追加しました"
            st.rerun()

# ====== 編集 ======
with col_edit:
    st.subheader("既存イベント編集")
    if not events:
        st.info("編集できるイベントがありません")
    else:
        ev = event_selectbox(events, key="edit_event_select")
        if ev is not None:
            with st.form("edit_event_form"):
                edit_cat = st.selectbox("カテゴリ", EVENT_CATEGORIES,
                                        index=EVENT_CATEGORIES.index(ev["category"]) if ev["category"] in EVENT_CATEGORIES else 0)
                edit_date = st.date_input(
                    "日付",
                    value=date.fromisoformat(ev["event_date"]) if ev["event_date"] else date.today()
                )
                edit_label = st.text_input("ラベル", value=ev["label"] or "")
                edit_note = st.text_area("メモ", value=ev["note"] or "")
                submitted_edit = st.form_submit_button("更新")

            if submitted_edit:
                if not edit_label:
                    st.error("ラベルを入力してください")
                else:
                    update_record("events", {"id": ev["id"]}, {
                        "category": edit_cat,
                        "event_date": edit_date.isoformat(),
                        "label": edit_label,
                        "note": edit_note or None,
                    })
                    st.session_state["_toast"] = f"✓ 更新しました: {edit_label}"
                    st.rerun()
