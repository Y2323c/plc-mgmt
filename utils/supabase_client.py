from supabase import create_client, Client
from utils.secrets import get_secret
from utils.constants import MS_ACTIVE, MS_PAUSED, M_STATUS_CAT_COACH

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = get_secret("SUPABASE_URL")
        key = get_secret("SUPABASE_KEY")
        _client = create_client(url, key)
    return _client


def get_members(active_only: bool = False) -> list[dict]:
    """全会員を display_name 付きで返す。active_only=True で在籍(1)・休会(2)のみ"""
    sb = get_client()
    q = sb.table("users_master").select("*")
    if active_only:
        q = q.in_("management_status", [MS_ACTIVE, MS_PAUSED])
    users = q.execute().data
    mappings = {m["user_id"]: m for m in sb.table("name_mappings").select("user_id, clean_name").execute().data}
    for u in users:
        nm = mappings.get(u["id"], {})
        u["display_name"] = nm.get("clean_name") or u["name"] or ""
    return sorted(users, key=lambda x: x["joined_at"] or "")


def get_coaches(include_room_id: bool = False) -> list[dict]:
    """コーチ一覧を返す。include_room_id=True で room_id も含む。"""
    sb = get_client()
    fields = "label, room_id" if include_room_id else "label"
    return sb.table("m_status").select(fields).eq("category", M_STATUS_CAT_COACH).order("code").execute().data


def get_m_status(category: str) -> list[dict]:
    """m_status から指定カテゴリのコード一覧を返す [{code, label}, ...]"""
    sb = get_client()
    return sb.table("m_status").select("code, label").eq("category", category).order("code").execute().data


def get_next_term_count(user_id: str) -> int:
    """coaching_tickets の MAX(term_count) + 1 を返す（既存なければ 1）"""
    sb = get_client()
    rows = sb.table("coaching_tickets").select("term_count").eq("user_id", user_id).execute().data
    if not rows:
        return 1
    return max(r["term_count"] or 0 for r in rows) + 1


def get_events() -> list[dict]:
    """events テーブルを日付降順で返す"""
    return get_client().table("events").select("*").order("event_date", desc=True).execute().data


def get_event_log(event_id: str, user_id: str) -> dict | None:
    """event_logs から (event_id, user_id) で1件取得"""
    rows = (
        get_client().table("event_logs")
        .select("*")
        .eq("event_id", event_id)
        .eq("user_id", user_id)
        .execute()
        .data
    )
    return rows[0] if rows else None


def upsert_event_log(event_id: str, user_id: str, display_name: str,
                     event_title: str, category: str, status: int,
                     checked_in_by: str | None = None,
                     note: str | None = None) -> None:
    """event_logs を upsert（既存なら UPDATE、なければ INSERT）"""
    existing = get_event_log(event_id, user_id)
    data = {
        "user_id": user_id,
        "event_id": event_id,
        "category": category,
        "title": event_title,
        "name": display_name,
        "status": status,
    }
    if checked_in_by is not None:
        data["checked_in_by"] = checked_in_by
    if note is not None:
        data["note"] = note
    sb = get_client()
    if existing:
        sb.table("event_logs").update(data).eq("id", existing["id"]).execute()
    else:
        sb.table("event_logs").insert(data).execute()


def upsert_record(table: str, data: dict) -> None:
    get_client().table(table).upsert(data).execute()


def insert_record(table: str, data: dict) -> None:
    get_client().table(table).insert(data).execute()


def update_record(table: str, match: dict, data: dict) -> None:
    q = get_client().table(table)
    for col, val in match.items():
        q = q.eq(col, val)
    q.update(data).execute()
