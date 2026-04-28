import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta

from utils.supabase_client import get_client, get_coaches
from utils.chatwork import send_message
from utils.secrets import get_secret
from utils.constants import LOG_TYPE_SESSION, COACHING_COMPLETION_ROOM_ID, M_STATUS_CAT_COACH
from utils.date_helpers import parse_date
from utils.coaching_config import REMINDERS, build_reminder_message
from utils.style import apply_style

apply_style()




def _status_label(elapsed: int, reminder_day: int, session_done: bool) -> str:
    if session_done:
        return "✅ 消化済み"
    days_until = reminder_day - elapsed
    if days_until > 0:
        return f"📅 あと{days_until}日"
    elif days_until == 0:
        return "🔔 今日"
    else:
        return f"⚠️ {abs(days_until)}日超過・未消化"


def _sort_key(label: str) -> int:
    if "超過" in label:
        n = int(label.replace("⚠️ ", "").split("日")[0])
        return -n
    if "今日" in label:
        return 0
    if "あと" in label:
        n = int(label.replace("📅 あと", "").replace("日", ""))
        return n
    return 9999




# ── データ取得 ───────────────────────────────────────────────────────────
st.title("コーチングリマインド確認")

sb    = get_client()
today = date.today()

# ── 全体キャンセル UI ─────────────────────────────────────────────────────
skip_data = (
    sb.table("reminder_skip_dates")
    .select("skip_date")
    .eq("skip_date", str(today))
    .execute()
    .data
)
skip_row = bool(skip_data)

with st.container(border=True):
    st.caption("⏸ 自動送信（18:00）は現在停止中。このページから手動で送信してください。")

st.divider()

# コーチ一覧（room_id・account_id も取得）
coaches_raw       = get_coaches(include_room_id=True, include_account_id=True)
all_coaches       = [c["label"] for c in coaches_raw]
coach_rooms       = {c["label"]: c.get("room_id")    for c in coaches_raw}
coach_account_ids = {c["label"]: c.get("account_id") for c in coaches_raw}

# フィルター
col_f1, col_f2 = st.columns([2, 3])
with col_f1:
    coach_filter = st.selectbox("コーチで絞り込み", ["全コーチ"] + all_coaches)
with col_f2:
    status_filter = st.selectbox(
        "ステータスで絞り込み",
        ["すべて", "明日の送信予定", "要対応のみ（超過・今日）", "未消化のみ", "消化済みを除く"],
    )

# 有効チケット取得
tickets = (
    sb.table("coaching_tickets").select("*")
    .eq("is_active", 1)
    .eq("send_reminder", True)
    .in_("coaching_type", list(REMINDERS.keys()))
    .execute().data
)

# user_id → {joined_at, cw_account} キャッシュ（全チケット対象）
all_user_ids = list({t["user_id"] for t in tickets if t.get("user_id")})
user_cache: dict[str, dict] = {}
if all_user_ids:
    users = (
        sb.table("users_master").select("id,joined_at,cw_account")
        .in_("id", all_user_ids).execute().data
    )
    user_cache = {u["id"]: {"joined_at": u.get("joined_at"), "cw_account": u.get("cw_account")} for u in users}

# コーチ account_id は後の coaches_raw で取得（重複取得を避けるため削除）

# セッションログを一括取得
ticket_ids = [t["id"] for t in tickets]
all_logs = []
if ticket_ids:
    all_logs = (
        sb.table("coaching_logs").select("ticket_id,session_count")
        .in_("ticket_id", ticket_ids)
        .eq("log_type", LOG_TYPE_SESSION)
        .execute().data
    )
done_map: dict[str, set] = {}
for log in all_logs:
    tid = log["ticket_id"]
    sc  = log.get("session_count")
    if sc is not None:
        done_map.setdefault(tid, set()).add(sc)

# ── テーブル構築（pass 1）────────────────────────────────────────────────
rows = []
for ticket in tickets:
    coaching_type     = ticket.get("coaching_type", "")
    coach_name        = ticket.get("coach_name", "")
    member_name       = ticket.get("name", "")
    ticket_id         = ticket["id"]
    user_id           = ticket.get("user_id", "")
    member_account_id = (user_cache.get(user_id) or {}).get("cw_account") or None

    if coach_filter != "全コーチ" and coach_name != coach_filter:
        continue

    if coaching_type == "新規コーチング":
        ref_str = (user_cache.get(user_id) or {}).get("joined_at")
    else:
        ref_str = ticket.get("start_date")

    ref_date = parse_date(ref_str or "")
    if not ref_date:
        ref_display = f"⚠️ 取得不可（{ref_str!r}）"
        elapsed = None
    else:
        ref_display = ref_date.strftime("%Y/%m/%d")
        elapsed = (today - ref_date).days

    done_sessions = done_map.get(ticket_id, set())

    for reminder in REMINDERS[coaching_type]:
        reminder_day = reminder["day"]
        session_num  = reminder["session"]
        months       = reminder["months"]
        session_done = session_num in done_sessions

        if elapsed is not None:
            status = _status_label(elapsed, reminder_day, session_done)
            remind_date_obj = ref_date + timedelta(days=reminder_day)
            remind_date     = remind_date_obj.strftime("%Y/%m/%d")
        else:
            status          = "⚠️ 基準日不明"
            remind_date     = "—"
            remind_date_obj = None

        rows.append({
            "_sort":              _sort_key(status) if elapsed is not None else 9998,
            "_months":            months,
            "_ticket_id":         ticket_id,
            "_session_num":       session_num,
            "_remind_date_raw":   remind_date_obj,
            "_member_account_id": member_account_id,
            "スキップ":           False,   # pass 2 で上書き
            "名前":               member_name,
            "コーチ":             coach_name,
            "種別":               coaching_type,
            "基準日":             ref_display,
            "経過日数":           elapsed if elapsed is not None else "—",
            "対象回":             f"{session_num}回目",
            "リマインド日":       remind_date,
            "状況":               status,
        })

# ステータスフィルター
def _apply_status_filter(row: dict) -> bool:
    s = row["状況"]
    if status_filter == "すべて":
        return True
    if status_filter == "明日の送信予定":
        return s == "📅 あと1日"
    if status_filter == "要対応のみ（超過・今日）":
        return "超過" in s or "今日" in s
    if status_filter == "未消化のみ":
        return "消化済み" not in s
    if status_filter == "消化済みを除く":
        return "消化済み" not in s
    return True

rows = [r for r in rows if _apply_status_filter(r)]
rows.sort(key=lambda r: r["_sort"])

# ── スキップ状態を DB からロード（pass 2）────────────────────────────────
remind_dates = list({
    str(r["_remind_date_raw"]) for r in rows if r["_remind_date_raw"] is not None
})
if remind_dates:
    skip_targets = (
        sb.table("reminder_skip_targets")
        .select("skip_date,ticket_id,session_num")
        .in_("skip_date", remind_dates)
        .execute().data
    )
    skip_set = {(r["skip_date"], r["ticket_id"], r["session_num"]) for r in skip_targets}
    for r in rows:
        if r["_remind_date_raw"] is not None:
            r["スキップ"] = (str(r["_remind_date_raw"]), r["_ticket_id"], r["_session_num"]) in skip_set

# ── 表示 ─────────────────────────────────────────────────────────────────
st.caption(f"基準日: 本日 {today.strftime('%Y/%m/%d')} / 対象チケット数: {len(tickets)}")

if not rows:
    st.info("表示対象のリマインドはありません。")
else:
    display_cols = ["スキップ", "名前", "コーチ", "種別", "基準日", "経過日数", "対象回", "リマインド日", "状況"]
    df = pd.DataFrame([{k: r[k] for k in display_cols} for r in rows])

    edited_df = st.data_editor(
        df,
        column_config={
            "スキップ": st.column_config.CheckboxColumn("スキップ", default=False),
        },
        disabled=[col for col in display_cols if col != "スキップ"],
        hide_index=True,
        use_container_width=True,
        key="reminder_table",
    )

    col_b1, col_b2 = st.columns([1, 2])

    # スキップ保存ボタン
    if col_b1.button("スキップを保存", use_container_width=True):
        changed = 0
        for i, row in enumerate(rows):
            old_skip = row["スキップ"]
            new_skip = bool(edited_df.iloc[i]["スキップ"])
            if old_skip == new_skip or row["_remind_date_raw"] is None:
                continue
            skip_key = {
                "skip_date":   str(row["_remind_date_raw"]),
                "ticket_id":   row["_ticket_id"],
                "session_num": row["_session_num"],
            }
            if new_skip:
                sb.table("reminder_skip_targets").upsert(skip_key).execute()
            else:
                (sb.table("reminder_skip_targets").delete()
                 .eq("skip_date",   skip_key["skip_date"])
                 .eq("ticket_id",   skip_key["ticket_id"])
                 .eq("session_num", skip_key["session_num"])
                 .execute())
            changed += 1
        if changed:
            st.toast(f"スキップを保存しました（{changed}件）", icon="✅")
            st.rerun()
        else:
            st.toast("変更はありませんでした", icon="ℹ️")

    # ── 手動送信セクション ────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📤 手動送信")

    # 今日・超過かつ未消化・スキップなしを対象候補とする
    send_candidates = [
        r for r in rows
        if not r["スキップ"] and ("今日" in r["状況"] or "超過" in r["状況"])
    ]

    if not send_candidates:
        st.caption("送信対象はありません（全員消化済み・スキップ済み、または対象日未到達）")
    else:
        st.caption(f"送信対象候補：{len(send_candidates)}件　｜　チェックを外すと送信しません")

        # 各人のチェックボックス＋メッセージ編集エリア
        send_flags: dict[int, bool] = {}
        edited_msgs: dict[int, str] = {}
        for i, r in enumerate(send_candidates):
            default_msg = build_reminder_message(
                r["種別"], r["_months"], r["_session_num"], r["名前"], r["コーチ"],
                member_account_id=r.get("_member_account_id"),
                coach_account_id=coach_account_ids.get(r["コーチ"]),
            )
            col_chk, col_detail = st.columns([1, 11])
            send_flags[i] = col_chk.checkbox("", value=True, key=f"send_sel_{i}")
            label = (
                f"**{r['名前']}**（{r['コーチ']}コーチ）"
                f"｜{r['種別']} {r['_session_num']}回目　{r['状況']}"
            )
            with col_detail.expander(label):
                edited_msgs[i] = st.text_area(
                    "送信内容（編集可）",
                    value=default_msg,
                    height=150,
                    key=f"msg_edit_{i}",
                )

        selected_with_idx = [(i, r) for i, r in enumerate(send_candidates) if send_flags.get(i)]

        st.write("")
        if selected_with_idx:
            if st.button(f"選択した {len(selected_with_idx)} 名に送信", type="primary"):
                token = get_secret("CHATWORK_COACHING_API_TOKEN")
                results = []
                for i, r in selected_with_idx:
                    # 救済コーチングは運用者専用ルーム、それ以外はコーチグループルーム
                    if r["種別"] == "救済コーチング":
                        room_id = COACHING_COMPLETION_ROOM_ID
                        dest    = "運用者ルーム"
                    else:
                        room_id = coach_rooms.get(r["コーチ"])
                        dest    = f"{r['コーチ']}グループ"

                    if not room_id:
                        results.append(f"❌ {r['名前']}（{r['コーチ']}：room_id 未設定）")
                        continue

                    # 編集済みメッセージを使用
                    msg = edited_msgs.get(i, "")
                    ok = send_message(str(room_id), msg, token=token or None)
                    results.append(
                        f"{'✅' if ok else '❌'} {r['名前']}（→ {dest}）"
                        f"　{r['種別']} {r['_session_num']}回目"
                    )
                    # 送信成功した行をスキップ登録
                    if ok and r["_remind_date_raw"] is not None:
                        sb.table("reminder_skip_targets").upsert({
                            "skip_date":   str(r["_remind_date_raw"]),
                            "ticket_id":   r["_ticket_id"],
                            "session_num": r["_session_num"],
                        }).execute()
                st.divider()
                for line in results:
                    st.write(line)
        else:
            st.caption("送信する人が選択されていません（チェックボックスを確認してください）")

    # サマリー
    st.divider()
    overdue   = sum(1 for r in rows if "超過" in r["状況"])
    today_cnt = sum(1 for r in rows if "今日" in r["状況"])
    upcoming  = sum(1 for r in rows if "あと" in r["状況"])
    done      = sum(1 for r in rows if "消化済み" in r["状況"])
    skipped   = sum(1 for r in rows if r["スキップ"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("⚠️ 超過・未消化", overdue)
    c2.metric("🔔 今日送信",     today_cnt)
    c3.metric("📅 予定あり",     upcoming)
    c4.metric("✅ 消化済み",     done)
    c5.metric("📵 スキップ",     skipped)
