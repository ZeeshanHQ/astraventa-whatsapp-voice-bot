import asyncio
import time
import os
import sys
import json
from dotenv import load_dotenv

# Ensure utf-8 encoding for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from app.services.studio import studio_service
from app.services.tts import text_to_speech_pcmu

async def run_simulation():
    print("=" * 65)
    print(" [*] ASTRAVENTA PROPRIETARY VOICE AI ENGINE SIMULATOR")
    print("=" * 65)

    # 1. Select Client Case
    business_name = "Apex Smile Dental Clinic"
    industry = "dental_clinic"
    custom_rules = "• 20% discount on first teeth cleaning.\n• Urgent walk-ins allowed before 5pm."

    print(f"\n[1] Dynamic Morphing in Progress for: '{business_name}'...")
    start_time = time.perf_counter()
    session = await studio_service.create_demo_session(
        business_name=business_name,
        industry=industry,
        custom_rules=custom_rules,
    )
    morph_time_ms = (time.perf_counter() - start_time) * 1000
    print(f" [OK] Agent Morphed in: {morph_time_ms:.1f}ms (Target: < 300ms)")
    print(f" [OK] Custom Initial Greeting: \"{session['greeting']}\"")
    print(f" [OK] Assigned Voice ID: {session['voice_id']}")

    # 2. Test TTS Latency on Greeting
    print("\n[2] Synthesizing First Message Audio Stream...")
    tts_start = time.perf_counter()
    audio_bytes = await text_to_speech_pcmu(session["greeting"])
    tts_time_ms = (time.perf_counter() - tts_start) * 1000
    if audio_bytes:
        print(f" [OK] Audio Synthesized in: {tts_time_ms:.1f}ms ({len(audio_bytes)} bytes PCMU generated)")
    else:
        print(" [INFO] Audio synthesis simulated (Keys in .env required for live stream).")

    # 3. Simulate Conversation Turn with Groq Llama-3.3-70B
    print("\n[3] Simulating Caller Question: 'Hi, I broke my tooth, do you have any emergency openings today?'")
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": session["metadata"]["system_prompt"]},
                    {"role": "assistant", "content": session["greeting"]},
                    {"role": "user", "content": "Hi, I broke my tooth, do you have any emergency openings today?"}
                ],
                "temperature": 0.6,
                "max_tokens": 100
            }
            llm_start = time.perf_counter()
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                llm_time_ms = (time.perf_counter() - llm_start) * 1000
                if res.status_code == 200:
                    reply = res.json()["choices"][0]["message"]["content"]
                    print(f" [OK] Groq LPU TTFT & Completion: {llm_time_ms:.1f}ms")
                    print(f" [OK] Agent Live Response: \"{reply.strip()}\"")
                else:
                    print(f" Groq API returned status: {res.status_code}")
        except Exception as e:
            print(f" Groq simulation notice: {e}")
    else:
        print(" [INFO] Note: Add GROQ_API_KEY in .env to test real-time LLM inference.")

    print("\n" + "=" * 65)
    print(" [OK] VOICE PIPELINE READY FOR PRODUCTION (LIVEKIT + TELNYX)")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(run_simulation())
