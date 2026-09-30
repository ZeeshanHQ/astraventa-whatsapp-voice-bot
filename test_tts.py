import asyncio
import sys
from app.services.tts import text_to_speech_pcmu

async def main():
    print("Starting synthesis...")
    audio = await text_to_speech_pcmu("Hello! This is a test of the emergency broadcast system.")
    print("Length of generated audio:", len(audio))
    if len(audio) > 0:
        print("First 100 bytes (hex):", audio[:100].hex())
        # Check if the bytes are all identical (like 0xff or 0x00)
        unique_bytes = set(audio)
        print("Number of unique bytes:", len(unique_bytes))
        print("Unique bytes sample:", list(unique_bytes)[:20])
    else:
        print("No audio generated!")

if __name__ == "__main__":
    asyncio.run(main())
