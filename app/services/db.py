import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from app.config import settings

logger = logging.getLogger("db_service")

supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Returns singleton Supabase client instance."""
    global supabase_client
    if supabase_client is not None:
        return supabase_client

    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            logger.info(f"Supabase client initialized for: {settings.SUPABASE_URL}")
            return supabase_client
        except Exception as exc:
            logger.error(f"Failed to initialize Supabase client: {exc}")

    return None


async def save_chat_message(wa_id: str, role: str, content: str) -> None:
    """Inserts a chat log message row into `chat_logs` table in Supabase."""
    client = get_supabase_client()
    if not client:
        logger.warning("Supabase client not available. Skipping chat log persistence.")
        return

    try:
        data = {
            "wa_id": wa_id,
            "role": role,
            "content": content,
        }
        res = client.table("chat_logs").insert(data).execute()
        logger.debug(f"Saved chat message for {wa_id} ({role}): {res.data}")
    except Exception as exc:
        logger.error(f"Error saving chat message for {wa_id}: {exc}")


async def fetch_chat_history(wa_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    Retrieves the last `limit` conversation turns for wa_id from `chat_logs` table,
    ordered chronologically. Returns list of {"role": str, "content": str}.
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        max_messages = limit * 2
        res = (
            client.table("chat_logs")
            .select("role, content, created_at")
            .eq("wa_id", wa_id)
            .order("created_at", desc=True)
            .limit(max_messages)
            .execute()
        )

        rows = res.data or []
        rows.reverse()

        return [{"role": r["role"], "content": r["content"]} for r in rows]

    except Exception as exc:
        logger.error(f"Error fetching chat history for {wa_id}: {exc}")
        return []


async def search_knowledge_base(
    query_embedding: List[float],
    match_threshold: float = 0.3,
    match_count: int = 3,
) -> List[Dict[str, Any]]:
    """
    Executes PostgreSQL RPC `match_knowledge_base` similarity search against vectors.
    """
    client = get_supabase_client()
    if not client or not query_embedding:
        return []

    try:
        params = {
            "query_embedding": query_embedding,
            "match_threshold": match_threshold,
            "match_count": match_count,
        }
        res = client.rpc("match_knowledge_base", params).execute()
        return res.data or []

    except Exception as exc:
        logger.error(f"Error searching knowledge base: {exc}")
        return []


async def seed_knowledge_base(content: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
    """Inserts a knowledge document with vector embedding into `knowledge_base` table."""
    client = get_supabase_client()
    if not client:
        return

    try:
        data = {
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
        }
        client.table("knowledge_base").insert(data).execute()
        logger.info(f"Seeded knowledge base document: {content[:50]}...")
    except Exception as exc:
        logger.error(f"Error seeding knowledge base: {exc}")


# ---------------------------------------------------------------------------
# Contact Settings (AI toggle per contact)
# ---------------------------------------------------------------------------

async def get_contact_ai_status(wa_id: str) -> bool:
    """
    Returns True if AI auto-reply is enabled for this contact (default True).
    If no record exists, AI is assumed enabled.
    """
    client = get_supabase_client()
    if not client:
        return True
    try:
        res = (
            client.table("contact_settings")
            .select("ai_enabled")
            .eq("wa_id", wa_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return bool(res.data[0]["ai_enabled"])
        return True  # Default: AI enabled
    except Exception as exc:
        logger.error(f"Error fetching AI status for {wa_id}: {exc}")
        return True


async def set_contact_ai_status(wa_id: str, ai_enabled: bool, contact_name: Optional[str] = None) -> None:
    """Upserts the AI enabled status for a contact in contact_settings."""
    client = get_supabase_client()
    if not client:
        return
    try:
        data: Dict[str, Any] = {"wa_id": wa_id, "ai_enabled": ai_enabled, "updated_at": "now()"}
        if contact_name is not None:
            data["contact_name"] = contact_name
        client.table("contact_settings").upsert(data, on_conflict="wa_id").execute()
        logger.info(f"Set AI status for {wa_id}: ai_enabled={ai_enabled}")
    except Exception as exc:
        logger.error(f"Error setting AI status for {wa_id}: {exc}")


async def get_all_contacts() -> List[Dict[str, Any]]:
    """
    Returns all unique contacts who have ever sent a message,
    enriched with their ai_enabled status and last message preview.
    """
    client = get_supabase_client()
    if not client:
        return []
    try:
        # Get all unique wa_ids with their last message and timestamp
        res = (
            client.table("chat_logs")
            .select("wa_id, role, content, created_at")
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        rows = res.data or []

        # Deduplicate: keep only the latest row per wa_id
        seen: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            wa_id = row["wa_id"]
            if wa_id not in seen:
                seen[wa_id] = row

        # Fetch all contact_settings
        settings_res = client.table("contact_settings").select("wa_id, ai_enabled, contact_name").execute()
        settings_map: Dict[str, Dict[str, Any]] = {
            s["wa_id"]: s for s in (settings_res.data or [])
        }

        contacts = []
        for wa_id, row in seen.items():
            s = settings_map.get(wa_id, {})
            contacts.append({
                "wa_id": wa_id,
                "contact_name": s.get("contact_name") or wa_id,
                "ai_enabled": s.get("ai_enabled", True),
                "last_message": row.get("content", "")[:80],
                "last_message_role": row.get("role", "user"),
                "last_seen": row.get("created_at", ""),
            })

        contacts.sort(key=lambda x: x["last_seen"], reverse=True)
        return contacts
    except Exception as exc:
        logger.error(f"Error fetching all contacts: {exc}")
        return []

