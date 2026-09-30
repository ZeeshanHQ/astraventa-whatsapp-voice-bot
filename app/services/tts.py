import asyncio
import logging
import subprocess
import edge_tts

logger = logging.getLogger("tts_service")

# A realistic free Edge TTS voice (English US)
DEFAULT_VOICE = "en-US-AriaNeural"

async def text_to_speech_pcmu(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """
    Synthesizes text to speech using edge-tts and converts it to G.711 PCMU (8kHz, mono)
    suitable for Telnyx real-time media streaming.

    Optimized for low latency: streams edge-tts MP3 chunks directly into ffmpeg stdin
    in real-time rather than buffering all audio first, reducing time-to-first-byte.
    """
    try:
        logger.info(f"Synthesizing text with edge-tts: '{text[:50]}...'")
        communicate = edge_tts.Communicate(text, voice)

        # Launch ffmpeg with stdin pipe: accepts raw MP3 stream, outputs raw PCMU mulaw
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-f", "mp3",         # Tell ffmpeg the input format is MP3
                "-i", "pipe:0",      # Read from stdin
                "-codec:a", "pcm_mulaw",
                "-f", "mulaw",
                "-ar", "8000",
                "-ac", "1",
                "pipe:1"             # Write to stdout
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL  # Suppress ffmpeg noise in logs
        )

        # Stream MP3 chunks from edge-tts directly into ffmpeg stdin as they arrive
        # This removes the full-buffer wait: ffmpeg starts decoding immediately
        mp3_bytes_sent = 0
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                process.stdin.write(chunk["data"])
                mp3_bytes_sent += len(chunk["data"])

        # Signal to ffmpeg that no more input is coming
        process.stdin.close()

        # Read all converted PCMU audio from ffmpeg stdout
        stdout = process.stdout.read()
        process.wait()

        if not stdout:
            logger.error("FFmpeg returned no PCMU audio output.")
            return b""

        logger.info(f"Successfully synthesized and converted {len(stdout)} bytes of PCMU audio (from {mp3_bytes_sent} bytes MP3).")
        return stdout

    except Exception as e:
        logger.error(f"Error in text_to_speech_pcmu: {e}", exc_info=True)
        return b""
