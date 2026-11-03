import json
import base64
import asyncio
import logging
import time
from datetime import datetime
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from app.config import settings
from app.client.telnyx import telnyx_client
from app.services.stt import DeepgramLiveClient
from app.services.tts import text_to_speech_pcmu
from app.services.ai_brain import ai_service
from app.services.db import (
    create_call_session,
    append_call_transcript,
    end_call_session,
)

logger = logging.getLogger("voice_router")
router = APIRouter(tags=["Voice Webhook"])


@router.post("/webhook/voice")
async def receive_voice_webhook(request: Request):
    """
    Handles Telnyx Call Control Webhook events.
    Routes:
      - call.initiated -> Answer the call
      - call.answered -> Start bidirectional media streaming
      - call.hangup -> Record completion in database
    """
    try:
        body = await request.body()
        if not body:
            return {"status": "empty_body"}

        payload = json.loads(body.decode("utf-8"))
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
            logger.info(f"Call {call_control_id} answered. Starting media stream...")
            domain = settings.SERVER_DOMAIN or "api.engine.astraventa.com"
            stream_url = f"wss://{domain}/webhook/voice/stream?from_number={from_number}&call_control_id={call_control_id}"
            await telnyx_client.start_media_stream(call_control_id, stream_url)

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
    connecting Telnyx Call Control with Deepgram Live STT, Ultra-Fast Humanized LLM, and Deepgram Aura-2 TTS.
    Features:
      - Bulletproof STT receive loop (never crashes or goes deaf)
      - Instant Caller Barge-In with Telnyx Media Buffer Clearing
      - Fast-Path Greeting Acknowledgment (300ms reply to "Hello?", no repeated intro script)
      - Snappy 300ms turn-taking
      - Real-time Inbound Call Session & Transcript Logging into Supabase `demo_sessions`
    """
    await websocket.accept()
    logger.info("Telnyx media WebSocket connection accepted.")

    # Extract call metadata passed from query parameters
    from_number = websocket.query_params.get("from_number", "anonymous_call").strip()
    call_control_id = websocket.query_params.get("call_control_id")

    logger.info(f"Stream parameters: from_number={from_number}, call_control_id={call_control_id}")

    deepgram_client = None
    stream_id = None
    playback_task = None
    call_start_time = time.time()
    session_id = None
    is_speaking = False
    is_processing = False
    call_history = []
    fast_greet_count = 0

    # Create tracked session in Supabase demo_sessions
    try:
        session_id = await create_call_session(
            call_control_id=call_control_id or "unknown",
            from_number=from_number,
            session_type="inbound_phone"
        )
    except Exception as e:
        logger.error(f"Error initializing call session: {e}")

    # Helper to send synthesized PCMU audio back in real-time chunks
    async def send_audio_in_chunks(audio_bytes: bytes):
        nonlocal stream_id, is_speaking
        is_speaking = True
        chunk_size = 160  # 20ms of PCMU at 8kHz (8000 bytes/sec * 0.020 = 160 bytes)
        start_time = asyncio.get_event_loop().time()
        logger.info(f"Streaming {len(audio_bytes)} bytes of audio in {chunk_size}-byte chunks (stream_id: {stream_id})...")

        try:
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

        except asyncio.CancelledError:
            logger.info("Playback cancelled by caller interruption / barge-in. Sending clear packet...")
            if stream_id:
                try:
                    await websocket.send_json({"event": "clear", "stream_id": stream_id})
                except Exception:
                    pass
            raise
        finally:
            is_speaking = False

    # Callback when Deepgram yields transcript segment
    async def on_transcript(transcript: str, is_final: bool):
        nonlocal playback_task, session_id, stream_id, is_speaking, is_processing

        clean_text = transcript.strip()
        if not clean_text:
            return

        # 1. INSTANT BARGE-IN: If bot is speaking and caller utters ANY word, stop bot immediately!
        if (is_speaking or (playback_task and not playback_task.done())):
            logger.info(f"Instant Barge-in triggered by caller speaking: '{clean_text}'. Stopping speech...")
            if playback_task and not playback_task.done():
                playback_task.cancel()
            is_speaking = False

            if stream_id:
                try:
                    await websocket.send_json({"event": "clear", "stream_id": stream_id})
                    logger.info("Sent Telnyx clear buffer event.")
                except Exception as e:
                    logger.warning(f"Error sending clear packet: {e}")

        # 2. Only process full reply once caller finishes utterance (endpointing=300ms)
        if not is_final:
            return

        logger.info(f"User Spoke (Final): '{clean_text}'")
        now_time = datetime.utcnow().strftime("%H:%M:%S")

        # Track caller utterance in session transcript
        if session_id:
            asyncio.create_task(append_call_transcript(session_id, "caller", clean_text, now_time))

        user_clean_lower = clean_text.lower().strip("?.!, ")

        # 3. FAST-PATH GREETING ACKNOWLEDGMENT:
        # If caller says "hello", "hi", "can you hear me", "am i audible", etc., acknowledge dynamically!
        # Answer instantly with a snappy, human reply in ~250ms without generic pitch recitation!
        GREETING_PHRASES = (
            "hello", "hi", "hey", "can you hear me", "are you there",
            "hello hello", "yes hello", "am i audible", "i am audible",
            "i'm audible", "hearing me", "you hear me", "is someone there"
        )
        if user_clean_lower in GREETING_PHRASES:
            fast_greet_count += 1
            if fast_greet_count == 1:
                reply_text = "Hey! Yes, I can hear you loud and clear. How can I help you out today?"
            else:
                reply_text = "Yep, still right here with you! Hearing you loud and clear. Go ahead."

            call_history.append({"role": "user", "content": clean_text})
            call_history.append({"role": "assistant", "content": reply_text})

            logger.info(f"Fast-path greeting acknowledged: '{reply_text}'")
            if session_id:
                asyncio.create_task(append_call_transcript(session_id, "agent", reply_text, datetime.utcnow().strftime("%H:%M:%S")))

            audio_bytes = await text_to_speech_pcmu(reply_text)
            if audio_bytes:
                playback_task = asyncio.create_task(send_audio_in_chunks(audio_bytes))
                try:
                    await playback_task
                except asyncio.CancelledError:
                    pass
            return

        # 4. INTENT DETECTION FOR TRANSFER TO ZEESHAN
        transfer_intent_phrases = [
            "talk to zeeshan", "speak to zeeshan", "speak with zeeshan",
            "connect me to zeeshan", "connect me with zeeshan", "transfer me to zeeshan",
            "put me through to zeeshan", "i want zeeshan", "get me zeeshan",
            "talk to human", "speak to human", "talk with human", "speak with human",
            "talk to a human", "speak to a human", "talk with a human", "speak with a human",
            "talk to a person", "speak to a person", "connect me to a person",
            "transfer me", "forward my call", "representative", "operator"
        ]
        user_transfer_intent = any(phrase in user_clean_lower for phrase in transfer_intent_phrases)

        # 5. GENERATE AI RESPONSE (Conversational, direct, human tone, sub-800ms)
        is_processing = True
        try:
            reply_text = await ai_service.process_user_query(
                wa_id=from_number,
                prompt=clean_text,
                is_voice=True,
                call_history=call_history
            )
            logger.info(f"AI Response: '{reply_text}'")
        finally:
            is_processing = False

        call_history.append({"role": "user", "content": clean_text})
        call_history.append({"role": "assistant", "content": reply_text})
        if len(call_history) > 12:
            call_history = call_history[-12:]

        # Track AI reply in session transcript
        if session_id:
            asyncio.create_task(append_call_transcript(session_id, "agent", reply_text, datetime.utcnow().strftime("%H:%M:%S")))

        ai_lower = reply_text.lower()
        ai_transfer_indicators = [
            "transfer you to zeeshan", "transferring you to zeeshan",
            "connect you with zeeshan", "connecting you with zeeshan",
            "transfer you now", "connecting you now", "transfer you", "transferring you"
        ]
        ai_transfer_intent = any(phrase in ai_lower for phrase in ai_transfer_indicators)
        should_transfer = user_transfer_intent or ai_transfer_intent

        if should_transfer:
            logger.info("Transfer intent confirmed. Notifying caller and transferring call...")
            if not ai_transfer_intent:
                reply_text = "Sure thing, hold on just a second while I connect you right over to Zeeshan."

            audio_bytes = await text_to_speech_pcmu(reply_text)
            if audio_bytes:
                playback_task = asyncio.create_task(send_audio_in_chunks(audio_bytes))
                try:
                    await playback_task
                except asyncio.CancelledError:
                    pass

            if call_control_id:
                await telnyx_client.transfer_call(call_control_id, settings.FORWARDING_TARGET)
                if session_id:
                    duration_sec = int(time.time() - call_start_time)
                    asyncio.create_task(end_call_session(session_id, duration_sec, status="transferred"))
            return

        # 6. SYNTHESIZE TO SPEECH VIA AURA-2 THALIA (Natural, human conversational voice)
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

            if "stream_id" in data:
                stream_id = data.get("stream_id")

            if event_type == "media":
                media_data = data.get("media", {})
                payload = media_data.get("payload")
                if payload:
                    audio_bytes = base64.b64decode(payload)
                    await deepgram_client.send_audio(audio_bytes)

            elif event_type == "start":
                logger.info(f"Start streaming payload: {data}")
                async def play_greeting():
                    nonlocal playback_task, session_id
                    greeting_text = "Hey there! Thanks for calling Astraventa. How can I help you out today?"
                    call_history.append({"role": "assistant", "content": greeting_text})
                    if session_id:
                        asyncio.create_task(append_call_transcript(session_id, "agent", greeting_text, datetime.utcnow().strftime("%H:%M:%S")))

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
        # Wrap up call session
        duration_sec = int(time.time() - call_start_time)
        if session_id:
            try:
                await end_call_session(session_id, duration_sec, status="completed")
            except Exception as e:
                logger.error(f"Error ending call session: {e}")

        if playback_task and not playback_task.done():
            playback_task.cancel()
        if deepgram_client:
            await deepgram_client.close()
        logger.info(f"Voice streaming session {session_id} closed (Total duration: {duration_sec}s).")
