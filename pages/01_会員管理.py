import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.supabase_client import get_client, get_members, get_m_status, insert_record
from utils.chatwork import find_account_id, get_dm_room_id, send_message
from utils.constants import ACTIVITY_TYPES, MS_LEFT, DATE_FMT_YM

st.title("会員管理")

sb = get_client()
members = get_members()
status_list = get_m_status("management_status")
status_options = {s["label"]: s["code"] for s in status_list}
status_labels = {s["code"]: s["label"] for s in status_list}

DEFAULT_TEMPLATE = "こんにちは。"

# session_state 初期化
if "new_member_saved" not in st.session_state:
    st.session_state["new_member_saved"] = None  # {"id", "name", "cw_account"}

def check_duplicates(display_name: str, email: str, cw_handle: str,
                     all_members: list, exclude_id: str | None = None) -> list[str]:
    """既存会員との重複をチェックし、警告メッセージのリストを返す"""
    warnings = []
    for m in all_members:
        if exclude_id and m.get("id") == exclude_id:
            continue
        if display_name and m.get("display_name", "").strip() == display_name.strip():
            warnings.append(f"表示名「{display_name}」は既に登録されています（{m['display_name']}）")
        if email and m.get("email") and m.get("email", "").strip().lower() == email.strip().lower():
            warnings.append(f"メールアドレス「{email}」は既に使用されています（{m['display_name']}）")
        if cw_handle and m.get("chatwork_id") and m.get("chatwork_id", "").strip() == cw_handle.strip():
            warnings.append(f"Chatwork ID「{cw_handle}」は既に登録されています（{m['display_name']}）")
    return warnings

# --- サイドバー ---
with st.sidebar:
    st.header("会員選択")
    mode = st.radio("モード", ["既存会員を編集", "新規追加"])

    selected = None
    if mode == "既存会員を編集":
        name_to_member = {m["display_name"]: m for m in members}
        selected_name = st.selectbox(
            "会員",
            list(name_to_member.keys()),
            index=None,
            placeholder="会員名を入力して選択",
        )
        if selected_name:
            selected = name_to_member[selected_name]

# モードが切り替わったら保存済み情報をリセット
if mode == "既存会員を編集":
    st.session_state["new_member_saved"] = None

# --- メインエリア ---
if mode == "新規追加" or selected:
    label = "新規追加" if mode == "新規追加" else f"編集: {selected['display_name']}"
    st.subheader(label)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**基本情報**")
        display_name = st.text_input(
            "表示名（clean_name）",
            value=selected["display_name"] if selected else "",
            placeholder="表示名を入力してください",
        )
        name = st.text_input(
            "本名（name）",
            value=selected.get("name") or "" if selected else "",
            placeholder="本名を入力してください",
        )
        try:
            _ja_default = datetime.strptime(selected.get("joined_at") or "", DATE_FMT_YM).date() if selected else date.today()
        except ValueError:
            _ja_default = date.today()
        _ja_date = st.date_input("入会月", value=_ja_default)
        joined_at = _ja_date.strftime(DATE_FMT_YM)
        left_at = st.text_input(
            "在籍有効期限（YYYY/MM）",
            value=selected.get("left_at") or "" if selected else "",
            placeholder="例: 2025/03",
        )

    with col2:
        st.markdown("**連絡先**")
        email = st.text_input(
            "メールアドレス",
            value=selected.get("email") or "" if selected else "",
            placeholder="メールアドレスを入力してください",
        )
        birthday = st.text_input(
            "誕生日（MM/DD）",
            value=selected.get("birthday") or "" if selected else "",
            placeholder="例: 04/15",
        )

        # Chatwork ID（文字列ハンドル）+ 自動取得ボタン
        st.markdown("**Chatwork**")
        cw_handle = st.text_input(
            "Chatwork ID（ハンドル名）",
            value=selected.get("chatwork_id") or "" if selected else "",
            placeholder="例: yamada_taro",
            key="cw_handle_input",
        )
        if st.button("アカウントID を自動取得", key="fetch_cw"):
            if not cw_handle:
                st.warning("Chatwork ID を入力してください")
            else:
                with st.spinner("検索中…"):
                    result = find_account_id(cw_handle)
                if result:
                    st.session_state["cw_account_input"] = str(result["account_id"])
                    st.success(f"✓ {result['name']}（ID: {result['account_id']}）")
                else:
                    st.error("見つかりませんでした。ハンドル名を確認してください")

        cw_account = st.text_input(
            "Chatwork Account ID（数字）※自動取得後も手動で修正できます",
            value=selected.get("cw_account") or "" if selected else "",
            placeholder="数字のアカウントID",
            key="cw_account_input",
        )

    with col3:
        st.markdown("**属性・備考**")
        current_code = selected.get("management_status") if selected else 1
        current_label = status_labels.get(int(current_code) if current_code is not None else 1, "在籍")
        status_label = st.selectbox(
            "在籍状況",
            list(status_options.keys()),
            index=list(status_options.keys()).index(current_label) if current_label in status_options else 1,
        )
        is_taikain = (status_options.get(status_label) == MS_LEFT)

        if mode == "既存会員を編集" and is_taikain:
            left_year = st.text_input(
                "退会日付",
                value=selected.get("left_year") or "" if selected else "",
                placeholder="例: 2025/03/31",
            )
        else:
            left_year = selected.get("left_year") if selected else None

        current_activity = selected.get("activity_type") if selected else None
        activity_idx = ACTIVITY_TYPES.index(current_activity) if current_activity in ACTIVITY_TYPES else None
        activity_type = st.selectbox(
            "活動タイプ",
            ACTIVITY_TYPES,
            index=activity_idx,
            placeholder="活動タイプを選択してください",
        )
        is_roadmap_active = st.checkbox(
            "ロードマップ有効",
            value=bool(int(selected.get("is_roadmap_active") or 0)) if selected else False,
        )
        note = st.text_area(
            "備考",
            value=selected.get("note") or "" if selected else "",
            placeholder="備考を入力してください",
        )

    # 重複チェック（新規追加時はリアルタイム表示）
    if mode == "新規追加":
        dup_warnings = check_duplicates(
            display_name, email, cw_handle, members,
            exclude_id=None
        )
        for w in dup_warnings:
            st.warning(f"⚠️ {w}")

    if st.button("保存", type="primary"):
        # 既存会員編集時は警告のみ（保存はブロックしない）
        if mode == "既存会員を編集":
            dup_warnings = check_duplicates(
                display_name, email, cw_handle, members,
                exclude_id=selected["id"]
            )
            for w in dup_warnings:
                st.warning(f"⚠️ {w}")

        status_code = status_options[status_label]
        user_data = {
            "name": name or display_name,
            "joined_at": joined_at or None,
            "left_at": left_at or None,
            "left_year": left_year or None,
            "management_status": status_code,
            "email": email or None,
            "birthday": birthday or None,
            "cw_account": cw_account or None,
            "chatwork_id": cw_handle or None,
            "activity_type": activity_type or None,
            "is_roadmap_active": 1 if is_roadmap_active else 0,
            "note": note or None,
        }
        if mode == "新規追加":
            new_id = str(uuid.uuid4())
            insert_record("users_master", {"id": new_id, **user_data})
            insert_record("name_mappings", {"user_id": new_id, "clean_name": display_name})
            st.success(f"✓ {display_name} を追加しました")
            # 入会メッセージ送信セクション用に保存
            st.session_state["new_member_saved"] = {
                "id": new_id,
                "name": display_name,
                "cw_account": cw_account,
            }
            st.session_state["cw_fetched_account_id"] = ""
        else:
            sb.table("users_master").update(user_data).eq("id", selected["id"]).execute()
            sb.table("name_mappings").update({"clean_name": display_name}).eq("user_id", selected["id"]).execute()
            st.success(f"✓ {display_name} を更新しました")
        st.cache_data.clear()

elif mode == "既存会員を編集":
    st.info("左のサイドバーから会員名を入力して選択してください")

# ── 入会メッセージ送信セクション ──────────────────────────────
new_member = st.session_state.get("new_member_saved")
if new_member:
    st.divider()
    st.subheader(f"入会メッセージ送信 — {new_member['name']}")

    if not new_member.get("cw_account"):
        st.warning("Chatwork Account ID が未設定のため送信できません。会員情報を編集して Account ID を追加してください。")
    else:
        message_body = st.text_area(
            "メッセージ内容（送信前に確認・加筆できます）",
            value=DEFAULT_TEMPLATE,
            height=160,
            key="message_body",
        )
        if st.button("Chatwork に送信", type="primary", key="send_cw"):
            with st.spinner("送信中…"):
                try:
                    room_id = get_dm_room_id(new_member["cw_account"])
                    if not room_id:
                        st.error("1対1チャットルームが見つかりませんでした。先に Chatwork で繋がっているか確認してください。")
                    else:
                        ok = send_message(room_id, message_body)
                        if ok:
                            # 履歴を保存
                            sb.table("message_logs").insert({
                                "user_id": new_member["id"],
                                "message_body": message_body,
                                "channel": "chatwork",
                                "status": "sent",
                                "note": f"room_id: {room_id}",
                            }).execute()
                            st.success("✓ 送信しました")
                            st.session_state["new_member_saved"] = None
                        else:
                            st.error("送信に失敗しました。APIトークンとルームIDを確認してください。")
                except Exception as e:
                    st.error(f"エラー: {e}")

        if st.button("送信せずに閉じる", key="close_msg"):
            st.session_state["new_member_saved"] = None
            st.rerun()

    # 送信履歴
    st.divider()
    st.subheader("送信履歴")
    logs = sb.table("message_logs").select("*, users_master(name)").order("sent_at", desc=True).limit(20).execute().data
    if logs:
        df_logs = pd.DataFrame([{
            "送信日時": l.get("sent_at", "")[:16].replace("T", " "),
            "宛先": (l.get("users_master") or {}).get("name", "—"),
            "ステータス": l.get("status", ""),
            "メッセージ冒頭": l.get("message_body", "")[:30] + "…" if len(l.get("message_body", "")) > 30 else l.get("message_body", ""),
        } for l in logs])
        st.dataframe(df_logs, use_container_width=True)
    else:
        st.info("送信履歴はまだありません")

# --- 一覧表示 ---
st.divider()
st.subheader("会員一覧")
filter_options = ["すべて"] + list(status_options.keys())
filter_label = st.selectbox(
    "在籍状況で絞り込み",
    filter_options,
    index=filter_options.index("在籍") if "在籍" in filter_options else 0,
)
display_members = members
if filter_label != "すべて":
    code = status_options[filter_label]
    display_members = [m for m in members if str(m.get("management_status")) == str(code)]

df = pd.DataFrame([{
    "表示名": m["display_name"],
    "入会月": m.get("joined_at") or "",
    "在籍状況": status_labels.get(int(m["management_status"]) if m.get("management_status") is not None else 0, ""),
    "活動タイプ": m.get("activity_type") or "",
    "メール": m.get("email") or "",
} for m in display_members])
st.dataframe(df, use_container_width=True)
