import streamlit as st
from collections import Counter, defaultdict
import pandas as pd
from utils.supabase_client import get_client, get_events, get_members
from utils.ui_helpers import event_selectbox

# ── データ取得 ──────────────────────────────────────────────
def _fetch_all_event_logs():
    """ページネーションで event_logs を全件取得"""
    sb = get_client()
    all_rows = []
    batch = 1000
    offset = 0
    while True:
        rows = (
            sb.table("event_logs")
            .select("event_id, status")
            .not_.is_("event_id", "null")
            .range(offset, offset + batch - 1)
            .execute()
            .data
        )
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch
    return all_rows

@st.cache_data(ttl=60)
def load_summary_data():
    events = get_events()
    logs   = _fetch_all_event_logs()
    members = get_members(active_only=False)
    active_count = sum(1 for m in members if m["management_status"] == 1)
    return events, logs, active_count

@st.cache_data(ttl=30)
def load_attendee_list(event_id: str):
    return (
        get_client()
        .table("event_logs")
        .select("user_id, name, status")
        .eq("event_id", event_id)
        .execute()
        .data
    )

# ── メイン ──────────────────────────────────────────────────
st.title("統計・レポート")

tab1, tab2 = st.tabs(["イベント別サマリー", "出席者リスト"])

# ── タブ①: イベント別サマリー ────────────────────────────
with tab1:
    events, logs, active_count = load_summary_data()

    # event_id ごとに status カウント
    counts: dict[str, Counter] = defaultdict(Counter)
    for row in logs:
        eid = row.get("event_id")
        if eid:
            counts[eid][row["status"]] += 1

    # 年フィルター
    years = sorted({e["event_date"][:4] for e in events if e.get("event_date")}, reverse=True)
    year_options = ["すべて"] + years
    selected_year = st.selectbox("年", year_options, key="summary_year")

    # テーブル構築
    rows = []
    for e in events:
        date_str = e.get("event_date") or ""
        if selected_year != "すべて" and not date_str.startswith(selected_year):
            continue
        eid = e["id"]
        c = counts.get(eid, Counter())
        attend  = c.get(1, 0)
        absent  = c.get(2, 0)
        plan_in = c.get(3, 0)
        plan_out= c.get(4, 0)
        no_ans  = max(active_count - attend - absent - plan_in - plan_out, 0)
        rate    = f"{attend / active_count * 100:.1f}%" if active_count else "—"
        rows.append({
            "カテゴリ":   e.get("category", ""),
            "日付":       date_str,
            "イベント名": e.get("label") or "—",
            "在籍者数":   active_count,
            "出席":       attend,
            "欠席":       absent,
            "参加予定":   plan_in,
            "欠席予定":   plan_out,
            "未回答":     no_ans,
            "出席率":     rate,
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(rows)} 件のイベント")
    else:
        st.info("該当するイベントがありません")

# ── タブ②: 出席者リスト ──────────────────────────────────
with tab2:
    events2, _, active_count2 = load_summary_data()
    selected_event = event_selectbox(events2, key="attendee_event")

    if selected_event:
        logs2 = load_attendee_list(selected_event["id"])

        # 在籍者全員（未回答検出用）
        all_members = get_members(active_only=False)
        active_members = {m["id"]: m["display_name"] for m in all_members if m["management_status"] == 1}

        logged_ids = {row["user_id"] for row in logs2}
        no_response_ids = set(active_members.keys()) - logged_ids

        attending  = [r for r in logs2 if r["status"] in (1, 3)]
        absent     = [r for r in logs2 if r["status"] in (2, 4)]

        STATUS_JP = {1: "出席", 2: "欠席", 3: "参加予定", 4: "欠席予定"}

        def show_group(title: str, items, use_name_key=True):
            st.markdown(f"**{title}（{len(items)}名）**")
            if not items:
                st.caption("なし")
            elif use_name_key:
                for r in sorted(items, key=lambda x: x.get("name", "")):
                    st.write(f"・{r.get('name', '—')}　{STATUS_JP.get(r['status'], '')}")
            else:
                for name in sorted(items):
                    st.write(f"・{name}")
            st.divider()

        show_group("出席・参加予定", attending)
        show_group("欠席・欠席予定", absent)

        no_resp_names = [active_members[uid] for uid in no_response_ids]
        show_group("未回答", no_resp_names, use_name_key=False)
    else:
        st.info("イベントを選択してください")
