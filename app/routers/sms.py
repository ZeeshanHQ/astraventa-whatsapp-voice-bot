import logging
from fastapi import APIRouter, Request, BackgroundTasks
from app.client.telnyx import telnyx_client
from app.services.ai_brain import ai_service

logger = logging.getLogger("sms_router")
router = APIRouter(tags=["SMS"])

async def process_sms_background(from_number: str, to_number: str, body: str):
    """
    Processes incoming SMS through Gemini AI and replies back using Telnyx Messaging API.
    All records are saved in Supabase chat logs automatically because process_user_query handles it.
    """
    try:
        logger.info(f"Processing SMS in background from {from_number}: {body}")
        
        # Use our existing AI service (processes prompt and updates Supabase history/memory)
        # We set is_voice=False to format responses properly for text SMS
        reply_text = await ai_service.process_user_query(wa_id=from_number, prompt=body, is_voice=False)
        
        logger.info(f"AI response generated for SMS: {reply_text}")
        
        # Send outbound SMS via Telnyx Messaging API
        await telnyx_client.send_sms(from_number=to_number, to_number=from_number, text=reply_text)
        
    except Exception as exc:
        logger.error(f"Error in process_sms_background: {exc}", exc_info=True)

@router.post("/webhook/sms")
async def receive_sms_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handles Telnyx inbound SMS Webhook events.
    Verifies that direction is inbound and event_type is message.received.
    Processes replies in a non-blocking background task.
    """
    try:
        payload = await request.json()
        data = payload.get("data", {})
        event_type = data.get("event_type")
        event_payload = data.get("payload", {})
        
        if event_type == "message.received":
            direction = event_payload.get("direction")
            
            # Only process inbound messages (avoid loopbacks of outbound SMS)
            if direction == "inbound":
                from_number = event_payload.get("from", {}).get("phone_number")
                to_number = event_payload.get("to", [{}])[0].get("phone_number")
                body = event_payload.get("body", "")
                
                logger.info(f"Inbound SMS received from {from_number} to {to_number}: {body}")
                
                if from_number and to_number and body:
                    # Run AI response generation and reply asynchronously in the background
                    background_tasks.add_task(process_sms_background, from_number, to_number, body)
                else:
                    logger.warning("SMS payload missing critical details (from, to, or body).")
            else:
                logger.debug(f"Ignoring outbound SMS event (direction: {direction})")
        else:
            logger.info(f"Received other Telnyx messaging event: {event_type}")
            
    except Exception as exc:
        logger.error(f"Error processing Telnyx SMS webhook: {exc}", exc_info=True)
        
    # Telnyx expects a 200 OK response instantly
    return {"status": "ok"}
