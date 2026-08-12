from supabase import create_client, Client
from app.core.config import settings

_client: Client | None = None


def get_db() -> Client:
    """Retorna cliente Supabase. Prefere SERVICE_KEY (bypass RLS),
    fallback para ANON_KEY se SERVICE_KEY não estiver configurada."""
    global _client
    if _client is None:
        key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
        _client = create_client(settings.SUPABASE_URL, key)
    return _client


async def get_setting(key: str) -> str | None:
    try:
        db = get_db()
        res = db.table("settings").select("value").eq("key", key).maybe_single().execute()
        return res.data["value"] if res and res.data else None
    except Exception:
        return None


async def update_setting(key: str, value: str) -> None:
    db = get_db()
    db.table("settings").update({"value": value}).eq("key", key).execute()


async def upsert_setting(key: str, value: str, description: str = "") -> None:
    db = get_db()
    db.table("settings").upsert(
        {"key": key, "value": value, "description": description},
        on_conflict="key"
    ).execute()
