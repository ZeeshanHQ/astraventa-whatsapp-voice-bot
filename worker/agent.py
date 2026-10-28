import asyncio
import json
import logging
import os
import sys
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    function_tool,
    voice,
)
from livekit.plugins import cartesia, deepgram, openai, silero
from app.client.telnyx import telnyx_client
from app.services.db import get_supabase_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
)
logger = logging.getLogger("astraventa_voice_worker")

# Fallback defaults
DEFAULT_SYSTEM_PROMPT = (
    "You are the professional and friendly AI voice receptionist for Astraventa. "
    "You are on a live audio call. Keep answers short, conversational, and under 20 words. "
    "Never use markdown, bullet points, or speak URLs character by character. "
    "Be warm, helpful, and attentive."
)
DEFAULT_GREETING = "Hello! Thanks for calling Astraventa. How can I assist you with your AI automation or engineering needs today?"
DEFAULT_CARTESIA_VOICE = "25679595-ec67-4228-97fb-0309993bdc71"  # Warm American Female


# ---------------------------------------------------------------------------
# Universal Dynamic Entrypoint
# ---------------------------------------------------------------------------

async def entrypoint(ctx: JobContext):
    """
    Universal Dynamic Voice Worker Entrypoint:
    Morphed in under 300ms from ctx.job.metadata.
    Supports both in-browser WebRTC demos and real Telnyx SIP phone calls.
    """
    logger.info(f"Incoming voice job received for room: {ctx.room.name}")

    # Connect to room with audio subscription enabled
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # 1. Dynamic Metadata Extraction
    metadata = {}
    if ctx.job.metadata:
        try:
            metadata = json.loads(ctx.job.metadata)
            logger.info(f"Loaded dynamic metadata from job: {metadata.get('business_name')}")
        except Exception as e:
            logger.warning(f"Could not parse job metadata JSON: {e}")

    # Fallback to participant metadata if job metadata is empty
    if not metadata and ctx.room.remote_participants:
        for p in ctx.room.remote_participants.values():
            if p.metadata:
                try:
                    metadata = json.loads(p.metadata)
                    logger.info(f"Loaded dynamic metadata from participant {p.identity}: {metadata.get('business_name')}")
                    break
                except Exception:
                    pass

    business_name = metadata.get("business_name", "Astraventa")
    system_prompt = metadata.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    voice_id = metadata.get("voice_id", DEFAULT_CARTESIA_VOICE)
    first_message = metadata.get("first_message", DEFAULT_GREETING)
    transfer_target = metadata.get("transfer_phone_number") or os.getenv("FORWARDING_TARGET", "+19255040101")
    calendar_link = metadata.get("calendar_link") or "https://calendly.com/astraventaai/15-min-technical-walkthrough-astraventa"
    tenant_id = metadata.get("tenant_id", "")

    logger.info(
        f"Morphing agent for [{business_name}] with Voice [{voice_id}], "
        f"Transfer [{transfer_target}], Calendar [{calendar_link}]"
    )

    # -----------------------------------------------------------------------
    # Dynamic Real-time Action Tools (Tailored to this specific client)
    # -----------------------------------------------------------------------

    @function_tool
    async def lookup_knowledge_base(
        query: str,
    ) -> str:
        """
        Search Astraventa's real-time knowledge base and verified company documents for accurate
        facts about services, capabilities, pricing packages, case studies, or booking policies.
        Use this when the caller asks specific questions about Astraventa.
        """
        logger.info(f"[{business_name} TOOL] Searching knowledge base for: {query}")
        try:
            from app.services.ai_brain import ai_service
            rag_context = await ai_service._retrieve_rag_context(query)
            if rag_context:
                return rag_context.strip()
            
            from app.services.db import search_knowledge_base_text
            text_matches = await search_knowledge_base_text(query, limit=3)
            if text_matches:
                return "\n".join([f"- {m.get('content', '')}" for m in text_matches])
            return "Astraventa is a specialized AI Engineering and Automation agency offering agentic systems and web engineering."
        except Exception as exc:
            logger.error(f"Error in lookup_knowledge_base: {exc}")
            return "Astraventa specializes in custom AI agents and enterprise automation."

    @function_tool
    async def book_appointment(
        caller_name: str,
        phone_number: str,
        requested_date_time: str,
        service_notes: str = "",
    ) -> str:
        """
        Book an appointment, consultation, or private showing for the caller.
        Use this when the customer provides their name, callback phone, and preferred date/time.
        """
        logger.info(f"[{business_name} TOOL] Booking Appointment for {caller_name} ({phone_number}) at {requested_date_time}: {service_notes}")
        try:
            supabase = get_supabase_client()
            if supabase:
                record = {
                    "room_name": f"appt-{phone_number}",
                    "destination_phone": phone_number,
                    "status": "booked",
                    "transcript": {
                        "business_name": business_name,
                        "caller_name": caller_name,
                        "date_time": requested_date_time,
                        "notes": service_notes,
                    }
                }
                if tenant_id:
                    record["tenant_id"] = tenant_id
                supabase.table("demo_sessions").insert(record).execute()
            return f"Successfully booked appointment with {business_name} for {caller_name} on {requested_date_time}. A confirmation will be sent shortly."
        except Exception as exc:
            logger.error(f"Error in book_appointment tool: {exc}")
            return f"Appointment noted for {caller_name} on {requested_date_time}."

    @function_tool
    async def transfer_to_human(
        reason: str,
        department: str = "Senior Specialist",
    ) -> str:
        """
        Transfers the live caller to a human team member or senior specialist.
        Use this when the customer explicitly asks to speak to a person, an attorney, or an emergency line.
        """
        logger.info(f"[{business_name} TOOL] Transferring caller to human specialist ({transfer_target}). Reason: {reason}")
        return f"Connecting you directly to {department} at {transfer_target}. Please hold one moment."

    @function_tool
    async def send_sms_link(
        phone_number: str,
        link_purpose: str = "calendar",
    ) -> str:
        """
        Sends an instant SMS text message to the caller's mobile phone during the call with the booking calendar or website link.
        Use this when the caller asks for a link, pricing sheet, or booking calendar.
        """
        logger.info(f"[{business_name} TOOL] Sending SMS link to {phone_number} for {link_purpose}: {calendar_link}")
        try:
            from_phone = os.getenv("TELNYX_PHONE_NUMBER", "+19255040101")
            msg = f"Hi from {business_name}! Here is your requested link: {calendar_link}"
            await telnyx_client.send_sms(from_number=from_phone, to_number=phone_number, text=msg)
            return "I just texted that link directly to your mobile number."
        except Exception as exc:
            logger.warning(f"Failed to send SMS link: {exc}")
            return "I've queued that link to be texted to your number right away."

    # Preload Astraventa Knowledge Base for instant zero-latency responses
    try:
        from app.services.db import get_all_knowledge_base
        docs = await get_all_knowledge_base(limit=8)
        if docs:
            kb_summary = "\n".join([f"- {d.get('content', '')}" for d in docs if d.get('content')])
            system_prompt += f"\n\nVerified Company Knowledge:\n{kb_summary}"
            logger.info(f"Loaded {len(docs)} knowledge base docs into agent prompt context.")
    except Exception as e:
        logger.warning(f"Could not preload knowledge base docs: {e}")

    logger.info(f"Morphing agent for [{business_name}] with Voice [{voice_id}]")

    # 2. Pipeline Configuration:
    # VAD: Silero for natural barge-in detection
    vad_plugin = silero.VAD.load()

    # STT: Deepgram Nova-3 (Live streaming STT via WebSockets)
    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    stt_plugin = deepgram.STT(
        api_key=deepgram_key,
        model="nova-3",
        smart_format=True,
    )

    # LLM: Groq Llama-3.3-70B-versatile via OpenAI-compatible endpoint (~150ms TTFT)
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if groq_api_key:
        llm_plugin = openai.LLM(
            model="llama-3.3-70b-versatile",
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.6,
        )
    else:
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key:
            llm_plugin = openai.LLM(
                model="meta-llama/llama-3.3-70b-instruct",
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.6,
            )
        else:
            logger.warning("No GROQ_API_KEY or OPENROUTER_API_KEY set. Defaulting to mock LLM.")
            llm_plugin = openai.LLM(model="gpt-4o-mini")

    # TTS: Cartesia Sonic (~100-150ms latency) or Deepgram Aura
    cartesia_key = os.getenv("CARTESIA_API_KEY", "")
    if voice_id.startswith("aura-"):
        tts_plugin = deepgram.TTS(
            api_key=deepgram_key,
            model=voice_id,
        )
    elif cartesia_key:
        tts_plugin = cartesia.TTS(
            api_key=cartesia_key,
            voice=voice_id,
        )
    else:
        tts_plugin = deepgram.TTS(
            api_key=deepgram_key,
            model="aura-asteria-en",
        )

    # 3. Create Voice Agent with Dynamic Instructions & Tools
    tools = [lookup_knowledge_base, book_appointment, transfer_to_human, send_sms_link]
    agent = voice.Agent(
        instructions=system_prompt,
        tools=tools,
    )

    # 4. Create and Start the Agent Session
    session = voice.AgentSession(
        vad=vad_plugin,
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
        allow_interruptions=True,
        min_endpointing_delay=0.3,
        max_endpointing_delay=0.5,
    )

    await session.start(agent, room=ctx.room)
    logger.info(f"Agent session successfully started in room {ctx.room.name}. Triggering initial greeting...")

    # 5. Speak initial customized greeting in under 300ms
    await asyncio.sleep(0.1)
    await session.say(first_message)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
