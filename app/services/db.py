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

    supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
    if settings.SUPABASE_URL and supabase_key:
        try:
            supabase_client = create_client(settings.SUPABASE_URL, supabase_key)
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



async def search_knowledge_base_text(query: str, limit: int = 4) -> List[Dict[str, Any]]:
    """
    Fallback keyword/text search against knowledge_base table when vector search
    is unavailable or returns low scores.
    """
    client = get_supabase_client()
    if not client or not query:
        return []

    try:
        keywords = [w.strip() for w in query.lower().split() if len(w.strip()) > 3]
        if not keywords:
            keywords = [query.strip()]

        matched_docs = []
        seen_ids = set()

        for kw in keywords[:3]:
            res = (
                client.table("knowledge_base")
                .select("id, content, metadata")
                .ilike("content", f"%{kw}%")
                .limit(limit)
                .execute()
            )
            for row in (res.data or []):
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    matched_docs.append(row)
                if len(matched_docs) >= limit:
                    break
            if len(matched_docs) >= limit:
                break

        if not matched_docs:
            res = (
                client.table("knowledge_base")
                .select("id, content, metadata")
                .order("id", desc=True)
                .limit(limit)
                .execute()
            )
            matched_docs = res.data or []

        return matched_docs

    except Exception as exc:
        logger.error(f"Error in search_knowledge_base_text: {exc}")
        return []


async def get_all_knowledge_base(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches all knowledge base documents for dashboard and voice worker preload."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        res = (
            client.table("knowledge_base")
            .select("id, content, metadata, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.error(f"Error fetching knowledge base: {exc}")
        return []


async def get_recent_call_sessions(limit: int = 20) -> List[Dict[str, Any]]:
    """Fetches recent demo and live call sessions for dashboard activity."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        res = (
            client.table("demo_sessions")
            .select("id, room_name, session_type, destination_phone, status, duration_seconds, transcript, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.error(f"Error fetching demo sessions: {exc}")
        return []


async def create_call_session(call_control_id: str, from_number: str, session_type: str = "inbound_phone") -> Optional[str]:
    """Creates a new tracked call session row in demo_sessions."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        short_id = from_number[-4:] if len(from_number) >= 4 else "0101"
        data = {
            "room_name": f"Call-{short_id}",
            "session_type": session_type,
            "destination_phone": from_number,
            "status": "in_progress",
            "duration_seconds": 0,
            "transcript": [],
        }
        res = client.table("demo_sessions").insert(data).execute()
        if res.data and len(res.data) > 0:
            session_id = str(res.data[0].get("id"))
            logger.info(f"Created tracked call session {session_id} for {from_number}")
            return session_id
    except Exception as exc:
        logger.error(f"Error creating call session for {from_number}: {exc}")
    return None


async def append_call_transcript(session_id: str, speaker: str, text: str, timestamp_str: str) -> None:
    """Appends a new turn to the session transcript in demo_sessions."""
    client = get_supabase_client()
    if not client or not session_id or not text:
        return
    try:
        res = client.table("demo_sessions").select("transcript").eq("id", session_id).execute()
        current_transcript = []
        if res.data and len(res.data) > 0:
            current_transcript = res.data[0].get("transcript") or []
            if not isinstance(current_transcript, list):
                current_transcript = []

        current_transcript.append({
            "speaker": speaker,
            "text": text,
            "time": timestamp_str,
        })

        client.table("demo_sessions").update({
            "transcript": current_transcript
        }).eq("id", session_id).execute()
    except Exception as exc:
        logger.error(f"Error appending transcript to session {session_id}: {exc}")


async def end_call_session(session_id: str, duration_seconds: int, status: str = "completed") -> None:
    """Updates session with final duration and completion status."""
    client = get_supabase_client()
    if not client or not session_id:
        return
    try:
        client.table("demo_sessions").update({
            "status": status,
            "duration_seconds": duration_seconds,
        }).eq("id", session_id).execute()
        logger.info(f"Closed call session {session_id}: status={status}, duration={duration_seconds}s")
    except Exception as exc:
        logger.error(f"Error closing call session {session_id}: {exc}")
