"""共通UIヘルパー"""
import streamlit as st
import pandas as pd
from utils.supabase_client import get_members
from utils.constants import MS_ACTIVE, MS_PAUSED


def member_selectbox(
    label: str = "会員",
    placeholder: str = "対象者のお名前を入れてください",
    key: str = "member",
    show_all_key: str = "show_all_members",
) -> dict | None:
    """
    会員選択セレクトボックス（在籍・休会フィルター＋全員表示切替付き）

    デフォルト: management_status 1（在籍）・2（休会）のみ表示
    チェックを入れると全会員を表示

    Returns:
        選択された会員の dict、未選択なら None
    """
    # 全会員をキャッシュして取得
    if "_all_members" not in st.session_state:
        st.session_state["_all_members"] = get_members(active_only=False)

    all_members = st.session_state["_all_members"]

    # フィルター切替チェックボックス
    show_all = st.checkbox("在籍・休会以外も表示", key=show_all_key, value=False)

    if show_all:
        filtered = all_members
    else:
        filtered = [m for m in all_members if m.get("management_status") in (MS_ACTIVE, MS_PAUSED)]

    name_to_member = {m["display_name"]: m for m in filtered}

    selected_name = st.selectbox(
        label,
        list(name_to_member.keys()),
        index=None,
        placeholder=placeholder,
        key=key,
    )

    if selected_name is None:
        return None
    return name_to_member[selected_name]


def event_selectbox(
    events: list[dict],
    key: str = "event",
    label: str = "イベント",
) -> dict | None:
    """
    イベント選択セレクトボックス
    表示形式: "{category} {label} {event_date}"

    Returns:
        選択されたイベントの dict、未選択なら None
    """
    event_labels = [
        f"{e['category']} {e['label'] or ''} {e['event_date'] or '日付未設定'}".strip()
        for e in events
    ]
    idx = st.selectbox(
        label,
        range(len(events)),
        format_func=lambda i: event_labels[i],
        index=None,
        placeholder="イベントを選択してください",
        key=key,
    )
    return events[idx] if idx is not None else None


def show_dataframe(
    data: list[dict],
    columns: dict,
    empty_msg: str = "記録がありません",
) -> None:
    """
    データフレーム表示の共通化。

    Args:
        data: レコードのリスト
        columns: {表示名: データキー} の辞書（順序が列順になる）
        empty_msg: data が空のときに表示するメッセージ
    """
    if not data:
        st.info(empty_msg)
        return
    rows = [{col_name: row.get(col_key, "") for col_name, col_key in columns.items()} for row in data]
    df = pd.DataFrame(rows)
    st.caption(f"{len(df)}件")
    st.dataframe(df, use_container_width=True, hide_index=True)
