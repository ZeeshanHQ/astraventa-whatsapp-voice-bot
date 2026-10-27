import asyncio
import logging
import subprocess
import httpx
from app.config import settings

logger = logging.getLogger("tts_service")

# Professional Deepgram Aura voice (natural, conversational English female)
DEFAULT_DEEPGRAM_VOICE = "aura-asteria-en"
DEFAULT_EDGE_VOICE = "en-US-AriaNeural"

async def text_to_speech_pcmu(text: str, voice: str = DEFAULT_DEEPGRAM_VOICE) -> bytes:
    """
    Synthesizes text to speech into raw G.711 PCMU (8kHz, mono mulaw) for Telnyx RTP audio streaming.
    Primary: Deepgram Aura TTS (ultra-low latency ~150-250ms, direct PCMU output, official API).
    Fallback: edge-tts piped through ffmpeg without deadlock.
    """
    if not text or not text.strip():
        return b""

    # 1. Primary: Deepgram Aura TTS
    if settings.DEEPGRAM_API_KEY:
        try:
            logger.info(f"Synthesizing text with Deepgram Aura TTS: '{text[:50]}...'")
            url = f"https://api.deepgram.com/v1/speak?model={voice}&encoding=mulaw&sample_rate=8000&container=none"
            headers = {
                "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {"text": text}
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200 and resp.content:
                    logger.info(f"Deepgram Aura TTS succeeded: {len(resp.content)} bytes PCMU generated.")
                    return resp.content
                else:
                    logger.warning(f"Deepgram Aura TTS returned status {resp.status_code}")
        except Exception as exc:
            logger.warning(f"Deepgram Aura TTS failed: {exc}, attempting fallback...")

    # 2. Fallback: Edge TTS + ffmpeg (non-blocking buffer safe)
    try:
        import edge_tts
        logger.info(f"Fallback: Synthesizing with edge-tts: '{text[:50]}...'")
        communicate = edge_tts.Communicate(text, DEFAULT_EDGE_VOICE)

        mp3_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])

        if not mp3_chunks:
            return b""

        all_mp3_data = b"".join(mp3_chunks)

        process = subprocess.Popen(
            [
                "ffmpeg",
                "-f", "mp3",
                "-i", "pipe:0",
                "-codec:a", "pcm_mulaw",
                "-f", "mulaw",
                "-ar", "8000",
                "-ac", "1",
                "pipe:1"
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        stdout, _ = process.communicate(input=all_mp3_data, timeout=8.0)

        if stdout:
            logger.info(f"Edge TTS fallback succeeded: {len(stdout)} bytes PCMU generated.")
            return stdout
    except Exception as e:
        logger.error(f"Fallback TTS failed: {e}")

    return b""
