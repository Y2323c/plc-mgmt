import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.supabase_client import get_client, get_m_status
from utils.ui_helpers import member_selectbox, show_dataframe
from utils.constants import CAT_WS, CAT_TEAM, CAT_CONSULT

st.title("受講生ログ")

sb = get_client()
mgmt_labels = {s["code"]: s["label"] for s in get_m_status("management_status")}

# --- サイドバー ---
with st.sidebar:
    st.header("会員選択")
    selected = member_selectbox(
        label="会員",
        placeholder="お名前を入れてください",
        key="member_log",
        show_all_key="show_all_log",
    )
    if selected is None:
        st.info("会員を選択してください")
        st.stop()
uid = selected["id"]

# --- 会員情報ヘッダー ---
status_label = mgmt_labels.get(selected.get("management_status"), "不明")
col1, col2, col3, col4 = st.columns(4)
col1.metric("氏名", selected["display_name"])
col2.metric("在籍状況", status_label)
col3.metric("入会月", selected.get("joined_at") or "—")
col4.metric("活動区分", selected.get("activity_type") or "—")

st.divider()

# --- タブ ---
tab_event, tab_consult, tab_ticket, tab_coaching = st.tabs([
    "WS・チーム参加", "コンサル", "コーチングチケット", "コーチング記録"
])

# ================================================
# タブ1: WS・チーム参加
# ================================================
with tab_event:
    logs = (
        sb.table("event_logs")
        .select("*, events(category, event_date, label)")
        .eq("user_id", uid)
        .in_("category", [CAT_WS, CAT_TEAM])
        .execute()
        .data
    )

    event_status_labels = {s["code"]: s["label"] for s in get_m_status("event_status")}

    rows = []
    for l in logs:
        ev = l.get("events") or {}
        rows.append({
            "カテゴリ": l["category"],
            "ラベル": ev.get("label") or l.get("title") or "",
            "日付": ev.get("event_date") or "",
            "ステータス": event_status_labels.get(l["status"] or 0, ""),
            "チェックイン担当": l.get("checked_in_by") or "",
        })
    show_dataframe(
        sorted(rows, key=lambda x: x["日付"], reverse=True),
        {"カテゴリ": "カテゴリ", "ラベル": "ラベル", "日付": "日付", "ステータス": "ステータス", "チェックイン担当": "チェックイン担当"}
    )

# ================================================
# タブ2: コンサル
# ================================================
with tab_consult:
    consults = (
        sb.table("event_logs")
        .select("*")
        .eq("user_id", uid)
        .eq("category", CAT_CONSULT)
        .execute()
        .data
    )

    show_dataframe(
        sorted([{"実施日": c.get("consult_date") or "", "種別": c.get("consult_type") or "", "メモ": c.get("note") or ""} for c in consults],
               key=lambda x: x["実施日"], reverse=True),
        {"実施日": "実施日", "種別": "種別", "メモ": "メモ"}
    )

# ================================================
# タブ3: コーチングチケット
# ================================================
with tab_ticket:
    tickets = (
        sb.table("coaching_tickets")
        .select("*")
        .eq("user_id", uid)
        .order("term_count")
        .execute()
        .data
    )

    show_dataframe(
        [{"期": t.get("term_count") or "", "種別": t.get("coaching_type") or "", "コーチ": t.get("coach_name") or "", "開始日": t.get("start_date") or "", "有効期限": t.get("expired_at") or "", "最大回数": t.get("max_sessions") or "", "期間(月)": t.get("duration_months") or "", "有効": "✅" if t.get("is_active") == 1 else "終了"} for t in tickets],
        {"期": "期", "種別": "種別", "コーチ": "コーチ", "開始日": "開始日", "有効期限": "有効期限", "最大回数": "最大回数", "期間(月)": "期間(月)", "有効": "有効"}
    )

# ================================================
# タブ4: コーチング記録
# ================================================
with tab_coaching:
    clogs = (
        sb.table("coaching_logs")
        .select("*")
        .eq("user_id", uid)
        .order("session_date")
        .execute()
        .data
    )

    show_dataframe(
        [{"種別": "セッション" if c.get("log_type") == "session" else "メモ", "期": c.get("term_count") or "", "回数": c.get("session_count") or "", "セッション日": c.get("session_date") or "", "次回予定": c.get("next_session_date") or "", "コーチ": c.get("coach_name") or "", "メモ": c.get("note") or ""} for c in clogs],
        {"種別": "種別", "期": "期", "回数": "回数", "セッション日": "セッション日", "次回予定": "次回予定", "コーチ": "コーチ", "メモ": "メモ"}
    )
