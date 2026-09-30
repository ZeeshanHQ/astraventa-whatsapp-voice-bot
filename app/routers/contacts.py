import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.db import (
    get_all_contacts,
    get_contact_ai_status,
    set_contact_ai_status,
    fetch_chat_history,
    save_chat_message,
)
from app.client.whatsapp import whatsapp_client

logger = logging.getLogger("contacts_router")
router = APIRouter(prefix="/api/contacts", tags=["Contacts"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ToggleAIRequest(BaseModel):
    ai_enabled: bool
    contact_name: Optional[str] = None


class SendMessageRequest(BaseModel):
    text: str


class NewConversationRequest(BaseModel):
    wa_id: str          # Phone number with country code e.g. 971501234567
    text: str
    contact_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_contacts():
    """
    Returns all contacts who have ever messaged, with ai_enabled status
    and last message preview. Used to populate the Inbox contact list.
    """
    contacts = await get_all_contacts()
    return {"contacts": contacts}


@router.get("/{wa_id}/history")
async def get_contact_history(wa_id: str, limit: int = 50):
    """Returns full chat history for a specific contact."""
    history = await fetch_chat_history(wa_id=wa_id, limit=limit)
    ai_enabled = await get_contact_ai_status(wa_id=wa_id)
    return {"wa_id": wa_id, "ai_enabled": ai_enabled, "messages": history}


@router.patch("/{wa_id}/toggle")
async def toggle_ai(wa_id: str, req: ToggleAIRequest):
    """
    Enables or disables AI auto-reply for a specific contact.
    When disabled, inbound messages from this contact are logged but not processed by AI.
    """
    await set_contact_ai_status(
        wa_id=wa_id,
        ai_enabled=req.ai_enabled,
        contact_name=req.contact_name,
    )
    status = "enabled" if req.ai_enabled else "disabled"
    logger.info(f"AI auto-reply {status} for contact {wa_id}")
    return {"wa_id": wa_id, "ai_enabled": req.ai_enabled, "status": f"AI auto-reply {status}"}


@router.post("/{wa_id}/send")
async def send_manual_message(wa_id: str, req: SendMessageRequest):
    """
    Sends a manual WhatsApp message to a contact from the dashboard.
    Only works when AI is disabled for that contact (human takeover mode).
    Saves the sent message to chat_logs as role='assistant'.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Message text cannot be empty.")

    try:
        response = await whatsapp_client.send_text_message(to=wa_id, text=req.text)
        await save_chat_message(wa_id=wa_id, role="assistant", content=req.text)
        logger.info(f"Manual message sent to {wa_id}: {req.text[:60]}...")
        return {"success": True, "wa_id": wa_id, "message": req.text, "api_response": response}
    except Exception as exc:
        logger.error(f"Failed to send manual message to {wa_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/new")
async def start_new_conversation(req: NewConversationRequest):
    """
    Starts a brand-new conversation with a phone number that has never messaged before.
    Sends first message and creates a contact_settings record with AI disabled by default
    (since you're manually initiating, you want to control the conversation).
    """
    wa_id = req.wa_id.strip().lstrip("+")

    if not wa_id or not req.text.strip():
        raise HTTPException(status_code=400, detail="wa_id and text are required.")

    try:
        response = await whatsapp_client.send_text_message(to=wa_id, text=req.text)
        # Save to chat_logs so contact appears in the inbox
        await save_chat_message(wa_id=wa_id, role="assistant", content=req.text)
        # Create contact record with AI disabled (manual outreach mode)
        await set_contact_ai_status(
            wa_id=wa_id,
            ai_enabled=False,
            contact_name=req.contact_name,
        )
        logger.info(f"New conversation started with {wa_id}: {req.text[:60]}...")
        return {"success": True, "wa_id": wa_id, "ai_enabled": False, "api_response": response}
    except Exception as exc:
        logger.error(f"Failed to start conversation with {wa_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
