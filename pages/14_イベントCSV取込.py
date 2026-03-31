import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.supabase_client import get_client, get_members, get_events, upsert_event_log
from utils.constants import ST_ATTENDED, ST_ABSENT, CAT_WS

st.title("イベントCSV取込")
st.caption("Google Formの回答CSVからWSの出欠実績を取り込みます。懇親会データは対象外です。")

# --- Step 1: イベント選択 ---
events = get_events()
ws_events = [e for e in events if e["category"] == CAT_WS]
if not ws_events:
    st.warning("WSイベントが登録されていません。先にイベント管理ページでWSを作成してください。")
    st.stop()

event_labels = {f"{e['event_date']}　{e['label']}": e for e in ws_events}
selected_label = st.selectbox("取込先イベント", list(event_labels.keys()))
selected_event = event_labels[selected_label]

# --- Step 2: CSVアップロード ---
uploaded = st.file_uploader("Google FormのCSVをアップロード", type="csv")
if not uploaded:
    st.info("CSVファイルをアップロードしてください")
    st.stop()

# --- Step 3: マッチング処理 ---
df = pd.read_csv(uploaded)

ws_col   = next((c for c in df.columns if "ワークショップ" in c), None)
note_col = next((c for c in df.columns if "備考" in c), None)

if not ws_col:
    st.error("「ワークショップに参加しますか？」列が見つかりません。CSVを確認してください。")
    st.stop()

members = get_members()
member_by_display = {m["display_name"]: m for m in members}


def _normalize(s: str) -> str:
    return str(s).replace(" ", "").replace("　", "").lower()


def _match_member(form_email: str, form_name: str):
    email = str(form_email).strip().lower()
    name  = str(form_name).strip()
    # ① メール完全一致
    for m in members:
        if m.get("email") and m["email"].lower() == email:
            return m, "メール"
    # ② 名前完全一致
    for m in members:
        if m["display_name"] == name or m["name"] == name:
            return m, "名前"
    # ③ スペース・大文字小文字を正規化して一致
    norm = _normalize(name)
    for m in members:
        if _normalize(m["display_name"]) == norm or _normalize(m.get("name", "")) == norm:
            return m, "名前（正規化）"
    return None, None


def _parse_ws(val: str):
    """WS列の値を (status, note) に変換"""
    v = str(val).strip()
    if "キャンセル" in v:
        return ST_ABSENT, "キャンセル"
    if "リアル" in v:
        return ST_ATTENDED, "リアル"
    if "オンライン" in v:
        return ST_ATTENDED, "オンライン"
    if "欠席" in v:
        return ST_ABSENT, None
    return None, None  # その他・空白


matched   = []
unmatched = []

for _, row in df.iterrows():
    form_email = str(row.get("メールアドレス", "") or "").strip()
    form_name  = str(row.get("お名前", "") or "").strip()
    ws_val     = str(row.get(ws_col, "") or "").strip()
    note_val   = str(row.get(note_col, "") or "").strip() if note_col else ""

    status, ws_note = _parse_ws(ws_val)
    note_str = " / ".join(filter(None, [ws_note, note_val])) or None

    member, match_type = _match_member(form_email, form_name)

    entry = {
        "form_name":  form_name,
        "form_email": form_email,
        "ws_val":     ws_val,
        "status":     status,
        "note_str":   note_str,
        "match_type": match_type,
        "member":     member,
    }
    (matched if member else unmatched).append(entry)


# --- Step 4: プレビュー ---
st.divider()

st.subheader(f"✅ 自動マッチ済み（{len(matched)}件）")
if matched:
    st.dataframe(
        [{
            "フォーム名":     e["form_name"],
            "会員名":        e["member"]["display_name"],
            "照合":          e["match_type"],
            "WS出欠":        e["ws_val"],
            "取込ステータス": "出席" if e["status"] == ST_ATTENDED else "欠席" if e["status"] == ST_ABSENT else "⚠️ 不明",
            "備考":          e["note_str"] or "",
        } for e in matched],
        use_container_width=True,
    )

st.divider()
st.subheader(f"⚠️ 未マッチ（{len(unmatched)}件）")
if unmatched:
    st.caption("会員が特定できませんでした。正しい会員を選択するか「スキップ」のままにしてください。")
    skip_opt = "（スキップ）"
    all_display = [skip_opt] + sorted(member_by_display.keys())

    for i, entry in enumerate(unmatched):
        col1, col2 = st.columns([2, 3])
        with col1:
            st.markdown(
                f"**{entry['form_name']}**  \n"
                f"{entry['form_email']}  \n"
                f"{entry['ws_val']}"
            )
        with col2:
            sel = st.selectbox(
                "会員を選択",
                all_display,
                key=f"unmatched_{i}",
                label_visibility="collapsed",
            )
            unmatched[i]["selected"] = sel
else:
    st.caption("全員マッチングできました。")

# --- Step 5: 取込確定 ---
st.divider()
importable_count = (
    sum(1 for e in matched   if e["status"] is not None) +
    sum(1 for e in unmatched if e.get("selected", "（スキップ）") != "（スキップ）" and e["status"] is not None)
)

if st.button(f"取込を確定（{importable_count}件）", type="primary", disabled=importable_count == 0):
    count  = 0
    errors = []

    for entry in matched:
        if entry["status"] is None:
            continue
        try:
            upsert_event_log(
                event_id=selected_event["id"],
                user_id=entry["member"]["id"],
                display_name=entry["member"]["display_name"],
                event_title=selected_event["label"],
                category=selected_event["category"],
                status=entry["status"],
                checked_in_by="CSVインポート",
                note=entry["note_str"],
            )
            count += 1
        except Exception as e:
            errors.append(f"{entry['form_name']}: {e}")

    for entry in unmatched:
        sel = entry.get("selected", "（スキップ）")
        if sel == "（スキップ）" or entry["status"] is None:
            continue
        member = member_by_display[sel]
        try:
            upsert_event_log(
                event_id=selected_event["id"],
                user_id=member["id"],
                display_name=member["display_name"],
                event_title=selected_event["label"],
                category=selected_event["category"],
                status=entry["status"],
                checked_in_by="CSVインポート",
                note=entry["note_str"],
            )
            count += 1
        except Exception as e:
            errors.append(f"{entry['form_name']}: {e}")

    st.success(f"✅ {count}件を取り込みました")
    if errors:
        st.error("エラーが発生した行：\n" + "\n".join(errors))
