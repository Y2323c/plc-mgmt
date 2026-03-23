"""Chatwork API ユーティリティ"""
import requests
from utils.secrets import get_secret

_BASE = "https://api.chatwork.com/v2"


def _headers() -> dict:
    token = get_secret("CHATWORK_API_TOKEN")
    if not token:
        raise ValueError("CHATWORK_API_TOKEN が設定されていません（.env または Streamlit Cloud secrets）")
    return {"X-ChatWorkToken": token}


def find_account_id(chatwork_id: str) -> dict | None:
    """
    Chatwork ハンドル名 (chatwork_id) からアカウント情報を返す。
    見つからない場合は None。
    戻り値: {"account_id": "123456", "name": "山田太郎"} など
    """
    res = requests.get(f"{_BASE}/contacts", headers=_headers(), timeout=10)
    res.raise_for_status()
    contacts = res.json()
    for c in contacts:
        if c.get("chatwork_id", "").lower() == chatwork_id.strip().lower():
            return {
                "account_id": str(c["account_id"]),
                "name":       c.get("name", ""),
                "avatar_image_url": c.get("avatar_image_url", ""),
            }
    return None


def get_dm_room_id(account_id: str) -> str | None:
    """
    指定アカウントとの 1対1 DM ルームIDを返す。
    見つからない場合は None。
    """
    res = requests.get(f"{_BASE}/rooms", headers=_headers(), timeout=10)
    res.raise_for_status()
    for room in res.json():
        if room.get("type") == "direct":
            # DM ルームのメンバーを確認
            members_res = requests.get(
                f"{_BASE}/rooms/{room['room_id']}/members",
                headers=_headers(),
                timeout=10,
            )
            if members_res.ok:
                member_ids = [str(m["account_id"]) for m in members_res.json()]
                if account_id in member_ids:
                    return str(room["room_id"])
    return None


def get_all_dm_room_ids() -> dict[str, str]:
    """
    全 DM ルームを取得し {account_id: room_id} の辞書を返す。
    一斉送信時に1度だけ呼び出してキャッシュすることで API 呼び出しを最小化する。
    """
    res = requests.get(f"{_BASE}/rooms", headers=_headers(), timeout=10)
    res.raise_for_status()
    dm_map: dict[str, str] = {}
    for room in res.json():
        if room.get("type") != "direct":
            continue
        room_id = str(room["room_id"])
        members_res = requests.get(
            f"{_BASE}/rooms/{room_id}/members",
            headers=_headers(),
            timeout=10,
        )
        if not members_res.ok:
            continue
        for m in members_res.json():
            aid = str(m["account_id"])
            if aid not in dm_map:
                dm_map[aid] = room_id
    return dm_map


def send_message(room_id: str, message: str) -> bool:
    """
    指定ルームにメッセージを送信する。
    成功で True、失敗で False。
    """
    res = requests.post(
        f"{_BASE}/rooms/{room_id}/messages",
        headers=_headers(),
        data={"body": message},
        timeout=10,
    )
    return res.ok
