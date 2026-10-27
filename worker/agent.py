import asyncio
import json
import logging
import os
import sys
from dotenv import load_dotenv

# Load root .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import cartesia, deepgram, openai, silero

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("astraventa_voice_worker")

# Fallback defaults if no dynamic metadata is passed
DEFAULT_SYSTEM_PROMPT = (
    "You are the professional and friendly AI receptionist for Astraventa. "
    "You are speaking on a live audio call. "
    "Keep all answers to one or two short sentences under 20 words. "
    "Never use markdown, bullet points, or speak URLs character by character. "
    "Be warm, helpful, and natural."
)
DEFAULT_GREETING = "Hello! Thanks for reaching out to Astraventa. How can I assist you today?"
DEFAULT_CARTESIA_VOICE = "25679595-ec67-4228-97fb-0309993bdc71"  # Warm American Female


async def entrypoint(ctx: JobContext):
    """
    Universal Dynamic Voice Worker Entrypoint:
    This worker handles ALL tenants, industries, and calls (both WebRTC in-browser
    and LiveKit SIP phone lines) from a single running process.
    """
    logger.info(f"Incoming voice job received for room: {ctx.room.name}")

    # Connect to room with audio subscription enabled
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # 1. Dynamic Metadata Extraction:
    # First inspect job metadata, then participant metadata if available
    metadata = {}
    if ctx.job.metadata:
        try:
            metadata = json.loads(ctx.job.metadata)
            logger.info(f"Loaded dynamic metadata from job: {metadata.get('business_name')}")
        except Exception as e:
            logger.warning(f"Could not parse job metadata JSON: {e}")

    # Fallback to inspecting participant metadata if job metadata was empty
    if not metadata and ctx.room.remote_participants:
        for p in ctx.room.remote_participants.values():
            if p.metadata:
                try:
                    metadata = json.loads(p.metadata)
                    logger.info(f"Loaded dynamic metadata from participant {p.identity}: {metadata.get('business_name')}")
                    break
                except Exception:
                    pass

    # Extract dynamic configuration fields
    business_name = metadata.get("business_name", "Astraventa")
    system_prompt = metadata.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    voice_id = metadata.get("voice_id", DEFAULT_CARTESIA_VOICE)
    first_message = metadata.get("first_message", DEFAULT_GREETING)

    logger.info(f"Morphing agent for [{business_name}] with Voice: [{voice_id}]")

    # 2. Configure Ultra-Low-Latency Brain & Speech Pipeline:
    # STT: Deepgram Nova-3 (streaming STT)
    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    stt_plugin = deepgram.STT(
        api_key=deepgram_key,
        model="nova-3",
        smart_format=True,
    )

    # VAD: Silero for natural sub-50ms barge-in interruptions
    vad_plugin = silero.VAD.load()

    # LLM: Groq Llama-3.3-70B via OpenAI-compatible endpoint (~150ms TTFT)
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if groq_api_key:
        llm_plugin = openai.LLM(
            model="llama-3.3-70b-versatile",
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.6,
        )
    else:
        # Fallback to standard OpenAI or OpenRouter if Groq is unset
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key:
            llm_plugin = openai.LLM(
                model="meta-llama/llama-3.3-70b-instruct",
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.6,
            )
        else:
            logger.warning("Neither GROQ_API_KEY nor OPENROUTER_API_KEY set. Defaulting to mock/demo LLM.")
            llm_plugin = openai.LLM(model="gpt-4o-mini")

    # TTS: Cartesia Sonic or Deepgram Aura (~100-150ms latency)
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
        # Default fallback to Deepgram Aura
        tts_plugin = deepgram.TTS(
            api_key=deepgram_key,
            model="aura-asteria-en",
        )

    # Construct the initial ChatContext with client-specific system instructions
    initial_chat_ctx = llm.ChatContext().append(
        role="system",
        text=system_prompt,
    )

    # 3. Assemble and Start the Voice Pipeline Agent
    agent = VoicePipelineAgent(
        vad=vad_plugin,
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
        chat_ctx=initial_chat_ctx,
        allow_interruptions=True,
        interrupt_speech_duration=0.4,  # 400ms speech triggers interruption
    )

    agent.start(ctx.room)
    logger.info(f"Agent started in room {ctx.room.name}. Triggering instant first message...")

    # 4. Speak initial custom greeting in under 300ms
    await asyncio.sleep(0.1)
    await agent.say(first_message, allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
