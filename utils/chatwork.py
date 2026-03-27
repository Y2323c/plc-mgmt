"""Chatwork API ユーティリティ"""
import requests
from utils.secrets import get_secret
from utils.constants import CHATWORK_API_BASE, CHATWORK_TIMEOUT


def _headers() -> dict:
    token = get_secret("CHATWORK_API_TOKEN")
    if not token:
        raise ValueError("CHATWORK_API_TOKEN が設定されていません（.env または Streamlit Cloud secrets）")
    return {"X-ChatWorkToken": token}


def _get(path: str) -> requests.Response:
    """共通 GET リクエスト"""
    res = requests.get(f"{CHATWORK_API_BASE}{path}", headers=_headers(), timeout=CHATWORK_TIMEOUT)
    res.raise_for_status()
    return res


def _post(path: str, data: dict) -> requests.Response:
    """共通 POST リクエスト"""
    return requests.post(
        f"{CHATWORK_API_BASE}{path}",
        headers=_headers(),
        data=data,
        timeout=CHATWORK_TIMEOUT,
    )


def find_account_id(chatwork_id: str) -> dict | None:
    """
    Chatwork ハンドル名 (chatwork_id) からアカウント情報を返す。
    見つからない場合は None。
    戻り値: {"account_id": "123456", "name": "山田太郎", "avatar_image_url": "..."}
    """
    contacts = _get("/contacts").json()
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
    rooms = _get("/rooms").json()
    for room in rooms:
        if room.get("type") != "direct":
            continue
        members_res = _get(f"/rooms/{room['room_id']}/members")
        member_ids = [str(m["account_id"]) for m in members_res.json()]
        if account_id in member_ids:
            return str(room["room_id"])
    return None


def get_all_dm_room_ids() -> dict[str, str]:
    """
    全 DM ルームを取得し {account_id: room_id} の辞書を返す。
    一斉送信時に1度だけ呼び出してキャッシュすることで API 呼び出しを最小化する。
    """
    rooms = _get("/rooms").json()
    dm_map: dict[str, str] = {}
    for room in rooms:
        if room.get("type") != "direct":
            continue
        room_id = str(room["room_id"])
        members_res = _get(f"/rooms/{room_id}/members")
        for m in members_res.json():
            aid = str(m["account_id"])
            if aid not in dm_map:
                dm_map[aid] = room_id
    return dm_map


def send_message(room_id: str, message: str, token: str | None = None) -> bool:
    """
    指定ルームにメッセージを送信する。
    token を指定した場合はそのトークンを使用（コーチング通知など別アカウント用）。
    成功で True、失敗で False。
    """
    headers = {"X-ChatWorkToken": token} if token else _headers()
    res = requests.post(
        f"{CHATWORK_API_BASE}/rooms/{room_id}/messages",
        headers=headers,
        data={"body": message},
        timeout=CHATWORK_TIMEOUT,
    )
    return res.ok
