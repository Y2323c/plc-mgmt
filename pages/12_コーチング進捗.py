import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import defaultdict
from datetime import date
import streamlit as st
import pandas as pd
from utils.supabase_client import get_client
from utils.constants import M_STATUS_CAT_COACH, LOG_TYPE_SESSION, LOG_TYPE_MEMO

st.title("コーチング進捗")

sb = get_client()

# ── コーチ一覧 ──────────────────────────────────────
_coaches_raw = (
    sb.table("m_status")
    .select("label")
    .eq("category", M_STATUS_CAT_COACH)
    .order("code")
    .execute()
    .data
)
COACH_LIST = [c["label"] for c in _coaches_raw if c["label"] != ".準備中"]
ALL_COACHES = "（全コーチ）"

# ── 全データ一括取得 ────────────────────────────────
all_tickets = (
    sb.table("coaching_tickets")
    .select("*")
    .eq("is_active", 1)
    .order("coach_name")
    .execute()
    .data
)

if not all_tickets:
    st.info("有効なチケットがありません。")
    st.stop()

all_ticket_ids = [t["id"] for t in all_tickets]
all_user_ids   = list({t["user_id"] for t in all_tickets})

members_raw = (
    sb.table("name_mappings")
    .select("user_id, clean_name")
    .in_("user_id", all_user_ids)
    .execute()
    .data
)
uid_to_name = {m["user_id"]: m["clean_name"] for m in members_raw}

all_logs = (
    sb.table("coaching_logs")
    .select("ticket_id, user_id, log_type, session_date, next_session_date, session_count, coach_name, note")
    .in_("ticket_id", all_ticket_ids)
    .order("session_date")
    .execute()
    .data
)

today      = date.today()
this_month = today.strftime("%Y-%m")


def _days_since(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return (today - date.fromisoformat(date_str.replace("/", "-"))).days
    except Exception:
        return None


def _ym(date_str: str | None) -> str:
    """'YYYY/MM/DD' → 'YYYY-MM'"""
    if not date_str or len(date_str) < 7:
        return ""
    return date_str[:7].replace("/", "-")


# ── タブ ────────────────────────────────────────────
tab_coach, tab_progress, tab_memos, tab_history = st.tabs([
    "📈 コーチ別サマリー", "📊 進捗", "💬 メモ", "📋 実施履歴"
])

# ===================================================
# 📈 コーチ別サマリー（第1タブ）
# ===================================================
with tab_coach:
    # URLパラメータがあれば初期値に使う
    param_coach = st.query_params.get("coach")
    coach_options = [ALL_COACHES] + COACH_LIST
    _default_idx = coach_options.index(param_coach) if param_coach in coach_options else 0

    selected_coach = st.selectbox(
        "コーチを選択（他タブに反映されます）",
        coach_options,
        index=_default_idx,
        key="coach_filter",
    )

    _input_url = f"/coaching?coach={selected_coach}" if selected_coach != ALL_COACHES else "/coaching"
    st.markdown(f'<a href="{_input_url}" target="_self">📝 記録入力ページへ →</a>', unsafe_allow_html=True)

    session_logs_all = [l for l in all_logs if l.get("log_type") == LOG_TYPE_SESSION]

    # コーチ別集計（常に全コーチ表示）
    coach_members:  dict[str, set] = defaultdict(set)
    coach_sessions: dict[str, int] = defaultdict(int)
    coach_monthly:  dict[str, int] = defaultdict(int)
    coach_last:     dict[str, str] = {}

    for t in all_tickets:
        cn = t.get("coach_name") or "未設定"
        coach_members[cn].add(t["user_id"])

    for l in session_logs_all:
        cn = l.get("coach_name") or "未設定"
        coach_sessions[cn] += 1
        if _ym(l.get("session_date")) == this_month:
            coach_monthly[cn] += 1
        sd = l.get("session_date") or ""
        if sd > coach_last.get(cn, ""):
            coach_last[cn] = sd

    summary_rows = sorted(
        [
            {
                "コーチ":     cn,
                "担当人数":   len(coach_members[cn]),
                "今月の実施": coach_monthly.get(cn, 0),
            }
            for cn in coach_members
        ],
        key=lambda x: x["今月の実施"],
        reverse=True,
    )
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # 月別コーチ別ピボット
    st.divider()
    st.subheader("月別コーチ別実施数")
    if session_logs_all:
        pivot_data: dict[tuple, int] = defaultdict(int)
        for l in session_logs_all:
            cn = l.get("coach_name") or "未設定"
            ym = _ym(l.get("session_date"))
            if ym:
                pivot_data[(cn, ym)] += 1

        coaches_in_pivot = sorted({k[0] for k in pivot_data})
        months_in_pivot  = sorted({k[1] for k in pivot_data}, reverse=True)

        pivot_rows = [
            {"コーチ": cn, **{ym: pivot_data.get((cn, ym), 0) for ym in months_in_pivot}}
            for cn in coaches_in_pivot
        ]
        st.dataframe(pd.DataFrame(pivot_rows), use_container_width=True, hide_index=True)
    else:
        st.info("セッション記録がありません。")


# ===================================================
# 以下タブ共通: coach_filter でフィルター
# ===================================================
_coach = st.session_state.get("coach_filter", ALL_COACHES)

# フィルター済みチケット・ログ
filtered_tickets = [
    t for t in all_tickets
    if _coach == ALL_COACHES or t.get("coach_name") == _coach
]
filtered_ids = {t["id"] for t in filtered_tickets}
filtered_uid = {t["user_id"] for t in filtered_tickets}

session_logs = [l for l in all_logs if l.get("log_type") == LOG_TYPE_SESSION and l["ticket_id"] in filtered_ids]
memo_logs    = [l for l in all_logs if l.get("log_type") == LOG_TYPE_MEMO    and l["ticket_id"] in filtered_ids]

ticket_sessions: dict[str, list] = defaultdict(list)
for l in session_logs:
    ticket_sessions[l["ticket_id"]].append(l)

uid_all_logs: dict[str, list] = defaultdict(list)
for l in all_logs:
    if l["ticket_id"] in filtered_ids:
        uid_all_logs[l["user_id"]].append(l)


# ===================================================
# 📊 進捗タブ
# ===================================================
with tab_progress:
    all_months = sorted({_ym(l["session_date"]) for l in session_logs if _ym(l["session_date"])}, reverse=True)
    month_options = ["全期間"] + all_months
    _month_default = month_options.index(this_month) if this_month in month_options else 0
    selected_month = st.selectbox("月でフィルター", month_options, index=_month_default, key="month_filter")

    rows = []
    for t in filtered_tickets:
        logs = ticket_sessions[t["id"]]
        session_count = len(logs)
        last_date  = logs[-1]["session_date"] if logs else None
        next_date  = logs[-1].get("next_session_date") if logs else None
        elapsed    = _days_since(last_date)
        max_sessions = t.get("max_sessions") or 0

        if selected_month != "全期間":
            month_count = sum(1 for l in logs if _ym(l["session_date"]) == selected_month)
            if month_count == 0:
                continue
        else:
            month_count = None

        row = {
            "コーチ":           t.get("coach_name") or "",
            "名前":             uid_to_name.get(t["user_id"], ""),
            "種別":             t.get("coaching_type") or "",
            "累計回数":         f"{session_count} / {max_sessions}" if max_sessions else str(session_count),
            "残り回数":         (max_sessions - session_count) if max_sessions else "—",
            "最終セッション日": last_date or "—",
            "経過日数":         elapsed if elapsed is not None else "—",
            "次回予定日":       next_date or "—",
        }
        if selected_month != "全期間":
            row["該当月の回数"] = month_count
        rows.append(row)

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(f"{selected_month} にセッションの記録がありません。" if selected_month != "全期間" else "記録がありません。")

    st.divider()
    st.subheader("月別セッション実施数")
    if session_logs:
        monthly: dict[str, int] = defaultdict(int)
        for l in session_logs:
            ym = _ym(l["session_date"])
            if ym:
                monthly[ym] += 1
        st.dataframe(
            pd.DataFrame(sorted(monthly.items(), reverse=True), columns=["年月", "実施数"]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("セッション記録がありません。")


# ===================================================
# 💬 メモタブ
# ===================================================
with tab_memos:
    if memo_logs:
        memo_rows = sorted(
            [
                {
                    "日付":   l.get("session_date") or "—",
                    "コーチ": l.get("coach_name") or "—",
                    "名前":   uid_to_name.get(l["user_id"], ""),
                    "メモ":   l.get("note") or "",
                }
                for l in memo_logs
            ],
            key=lambda x: x["日付"],
            reverse=True,
        )
        st.dataframe(pd.DataFrame(memo_rows), use_container_width=True, hide_index=True)
    else:
        st.info("メモがありません。")


# ===================================================
# 📋 実施履歴タブ
# ===================================================
with tab_history:
    member_options = sorted(uid_to_name[uid] for uid in filtered_uid if uid in uid_to_name)
    if not member_options:
        st.info("メンバーがいません。")
    else:
        selected_name = st.selectbox("メンバーを選択", member_options, key="history_member")
        selected_uid  = next((uid for uid, name in uid_to_name.items() if name == selected_name), None)

        if selected_uid:
            logs = sorted(uid_all_logs[selected_uid], key=lambda x: x.get("session_date") or "")
            if logs:
                history_rows = [
                    {
                        "種別":     "セッション" if l.get("log_type") == LOG_TYPE_SESSION else "メモ",
                        "回":       l.get("session_count") or "—",
                        "日付":     l.get("session_date") or "—",
                        "次回予定": l.get("next_session_date") or "—",
                        "コーチ":   l.get("coach_name") or "—",
                        "メモ":     l.get("note") or "",
                    }
                    for l in logs
                ]
                st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
            else:
                st.info("記録がありません。")
