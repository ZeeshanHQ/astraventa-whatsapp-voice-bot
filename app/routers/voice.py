import json
import base64
import asyncio
import logging
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from app.config import settings
from app.client.telnyx import telnyx_client
from app.services.stt import DeepgramLiveClient
from app.services.tts import text_to_speech_pcmu
from app.services.ai_brain import ai_service

logger = logging.getLogger("voice_router")
router = APIRouter(tags=["Voice Webhook"])

@router.post("/webhook/voice")
async def receive_voice_webhook(request: Request):
    """
    Handles Telnyx Call Control Webhook events.
    Routes:
      - call.initiated -> Answer the call
      - call.answered -> Start bidirectional media streaming
    """
    try:
        payload = await request.json()
        data = payload.get("data", {})
        event_type = data.get("event_type")
        event_payload = data.get("payload", {})
        call_control_id = event_payload.get("call_control_id")
        from_number = event_payload.get("from")
        to_number = event_payload.get("to")
        direction = event_payload.get("direction", "incoming")

        logger.info(f"Received Telnyx event: '{event_type}' (direction: {direction}) for call_control_id: {call_control_id}")

        if event_type == "call.initiated":
            if direction != "incoming":
                logger.info(f"Ignoring outgoing/transferred call leg initiation for call_control_id: {call_control_id}")
                return {"status": "ignored"}

            logger.info(f"Incoming call initiated from {from_number} to {to_number}. Answering...")
            await telnyx_client.answer_call(call_control_id)

        elif event_type == "call.answered":
            logger.info(f"Call {call_control_id} answered. Direct forwarding to {settings.FORWARDING_TARGET}...")
            await telnyx_client.transfer_call(call_control_id, settings.FORWARDING_TARGET)

        elif event_type == "call.hangup":
            hangup_cause = event_payload.get("hangup_cause", "unknown")
            sip_status = event_payload.get("sip_status", "unknown")
            logger.info(f"Call {call_control_id} hung up. Cause: {hangup_cause}, SIP Status: {sip_status}")

    except Exception as exc:
        logger.error(f"Error handling Telnyx webhook: {exc}", exc_info=True)

    return {"status": "ok"}


@router.websocket("/webhook/voice/stream")
async def voice_websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint handling raw bi-directional audio stream (PCMU over WebSocket)
    connecting Telnyx Call Control with Deepgram Live STT, Gemini RAG, and edge-tts.
    """
    await websocket.accept()
    logger.info("Telnyx media WebSocket connection accepted.")

    # Extract call metadata passed from query parameters
    from_number = websocket.query_params.get("from_number", "anonymous_call")
    call_control_id = websocket.query_params.get("call_control_id")

    logger.info(f"Stream parameters: from_number={from_number}, call_control_id={call_control_id}")

    deepgram_client = None
    stream_id = None
    playback_task = None

    # Helper to send synthesized PCMU audio back in real-time chunks (prevents silence/buffer errors)
    async def send_audio_in_chunks(audio_bytes: bytes):
        nonlocal stream_id
        chunk_size = 160  # 20ms of PCMU at 8kHz (8000 bytes/sec * 0.020 = 160 bytes)
        start_time = asyncio.get_event_loop().time()
        logger.info(f"Streaming {len(audio_bytes)} bytes of audio in {chunk_size}-byte chunks (stream_id: {stream_id})...")
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i + chunk_size]
            base64_chunk = base64.b64encode(chunk).decode("utf-8")
            
            payload = {
                "event": "media",
                "media": {
                    "payload": base64_chunk
                }
            }
            if stream_id:
                payload["stream_id"] = stream_id

            await websocket.send_json(payload)
            
            # Drift-corrected sleep to maintain precise 20ms playback pacing
            next_chunk_index = i + chunk_size
            expected_time = start_time + (next_chunk_index / 8000.0)
            now = asyncio.get_event_loop().time()
            sleep_duration = expected_time - now
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)

    # Callback when Deepgram yields transcript segment
    async def on_transcript(transcript: str, is_final: bool):
        nonlocal playback_task

        # Cancel active playback only if user is clearly speaking (at least 3 words in interim)
        # This prevents background noise, breathing, or call connection artifacts from killing the greeting
        word_count = len(transcript.strip().split()) if transcript.strip() else 0
        if playback_task and not playback_task.done() and word_count >= 3:
            playback_task.cancel()
            logger.info(f"Cancelled active playback task due to user barge-in ({word_count} words detected).")
            try:
                await playback_task
            except asyncio.CancelledError:
                pass

        # Only process query and respond if the segment is finalized
        if not is_final:
            return

        logger.info(f"User Spoke (Final): '{transcript}'")

        # Intent detection keywords for user transcript
        user_lower = transcript.lower()
        transfer_intent_phrases = [
            "talk to zeeshan",
            "speak to zeeshan",
            "speak with zeeshan",
            "connect me to zeeshan",
            "connect me with zeeshan",
            "transfer me to zeeshan",
            "put me through to zeeshan",
            "i want zeeshan",
            "get me zeeshan",
            "talk to human",
            "speak to human",
            "talk with human",
            "speak with human",
            "talk to a human",
            "speak to a human",
            "talk with a human",
            "speak with a human",
            "talk with any person",
            "talk to any person",
            "speak with any person",
            "speak to any person",
            "talk to a person",
            "talk with a person",
            "speak to a person",
            "speak with a person",
            "connect me to a person",
            "connect me with a person",
            "connect me to human",
            "connect me with human",
            "talk to someone",
            "talk to somebody",
            "speak to someone",
            "speak to somebody",
            "transfer me",
            "forward my call",
            "call transfer",
            "representative",
            "operator",
            "agent",
        ]
        user_transfer_intent = any(phrase in user_lower for phrase in transfer_intent_phrases)

        # Process the transcript through Gemini RAG (shares user history by from_number)
        reply_text = await ai_service.process_user_query(wa_id=from_number, prompt=transcript, is_voice=True)
        logger.info(f"AI Response: '{reply_text}'")

        # Intent detection in AI response (handles STT errors like "Vishan"/"Nishan")
        ai_lower = reply_text.lower()
        ai_transfer_indicators = [
            "transfer you to zeeshan",
            "transferring you to zeeshan",
            "connect you with zeeshan",
            "connecting you with zeeshan",
            "connect you to zeeshan",
            "connecting you to zeeshan",
            "put you through to zeeshan",
            "putting you through to zeeshan",
            "transfer you now",
            "transferring you now",
            "connecting you now",
            "transfer you",
            "transferring you",
            "connect you",
            "connecting you",
            "put you through",
            "putting you through"
        ]
        ai_transfer_intent = any(phrase in ai_lower for phrase in ai_transfer_indicators)

        should_transfer = user_transfer_intent or ai_transfer_intent

        if should_transfer:
            logger.info(f"Transfer intent detected (User intent: {user_transfer_intent}, AI intent: {ai_transfer_intent})")
            # If the AI response itself doesn't mention transfer, inject a default notice
            if not ai_transfer_intent:
                reply_text = "Sure, please hold while I put you through to Zeeshan."

            audio_bytes = await text_to_speech_pcmu(reply_text)
            if audio_bytes:
                playback_task = asyncio.create_task(send_audio_in_chunks(audio_bytes))
                try:
                    await playback_task
                except asyncio.CancelledError:
                    logger.info("Playback of transfer notice was cancelled.")
                    return

            # Issue transfer command to Telnyx
            if call_control_id:
                await telnyx_client.transfer_call(call_control_id, settings.FORWARDING_TARGET)
            return

        # Regular reply: Synthesize to PCMU G.711 mulaw using edge-tts
        audio_bytes = await text_to_speech_pcmu(reply_text)
        if audio_bytes:
            playback_task = asyncio.create_task(send_audio_in_chunks(audio_bytes))
            try:
                await playback_task
            except asyncio.CancelledError:
                logger.info("Playback of audio reply was cancelled.")
                return

    # Initialize and connect Deepgram Live client
    deepgram_client = DeepgramLiveClient(on_transcript_received=on_transcript)
    connected = await deepgram_client.connect()
    if not connected:
        logger.error("Could not establish Deepgram connection. Aborting WebSocket stream.")
        await websocket.close()
        return

    try:
        while True:
            # Receive streaming messages from Telnyx
            message = await websocket.receive_text()
            data = json.loads(message)
            event_type = data.get("event")

            # Capture stream_id dynamically if available in any event
            if "stream_id" in data:
                stream_id = data.get("stream_id")

            if event_type == "media":
                media_data = data.get("media", {})
                payload = media_data.get("payload")
                if payload:
                    # Decode base64 raw audio bytes
                    audio_bytes = base64.b64decode(payload)
                    # Stream to Deepgram
                    await deepgram_client.send_audio(audio_bytes)

            elif event_type == "start":
                logger.info(f"Start streaming payload: {data}")
                # Play greeting immediately upon call start in a non-blocking background task
                async def play_greeting():
                    nonlocal playback_task
                    greeting_text = "Hello! Thanks for calling Astraventa. How can I help you today?"
                    audio_bytes = await text_to_speech_pcmu(greeting_text)
                    if audio_bytes:
                        playback_task = asyncio.create_task(send_audio_in_chunks(audio_bytes))
                        try:
                            await playback_task
                            logger.info("Finished streaming welcome greeting.")
                        except asyncio.CancelledError:
                            logger.info("Welcome greeting playback was cancelled.")
                
                asyncio.create_task(play_greeting())
            else:
                logger.info(f"Received other Telnyx event: {data}")

    except WebSocketDisconnect:
        logger.info("Telnyx media WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Error in Telnyx media streaming WebSocket: {e}", exc_info=True)
    finally:
        if playback_task and not playback_task.done():
            playback_task.cancel()
            logger.info("Cancelled active playback task during WebSocket cleanup.")
        if deepgram_client:
            await deepgram_client.close()
        logger.info("Voice streaming connection fully closed.")
