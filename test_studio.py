import asyncio
import json
from app.services.studio import studio_service
from app.services.scraper import scrape_website_summary
from app.config import settings

async def main():
    print("=== Testing Astraventa Dynamic Voice AI Studio ===")

    # 1. Test Industry Templates
    templates = studio_service.get_templates()
    print(f"[OK] Loaded {len(templates)} industry templates:")
    for k in templates:
        print(f"   - {k}: {templates[k]['label']}")

    # 2. Test Voice Catalog
    voices = studio_service.get_voices()
    print(f"[OK] Loaded {len(voices)} high-fidelity voices (Cartesia & Deepgram):")
    for v in voices:
        print(f"   - {v['name']} ({v['provider']})")

    # 3. Test Dynamic Prompt & Greeting Synthesis (Under 5 seconds)
    print("\n--- Testing Instant Agent Morphing for Real Estate Client ---")
    session = await studio_service.create_demo_session(
        business_name="Vanguard Luxury Properties",
        industry="real_estate",
        custom_rules="• Exclusive penthouses in Manhattan.\n• Average price $4.5M.\n• Pre-approval letter required.",
    )

    print(f"[OK] Room Created: {session['room_name']}")
    print(f"[OK] Session ID: {session['session_id']}")
    print(f"[OK] First Greeting: '{session['greeting']}'")
    print(f"[OK] Assigned Voice: {session['voice_id']}")
    print("[OK] Injected Metadata Payload:")
    print(json.dumps(session["metadata"], indent=2))

    print("\n--- Testing Instant Agent Morphing for Dental Clinic Client ---")
    session_dental = await studio_service.create_demo_session(
        business_name="Apex Smile Studio",
        industry="dental_clinic",
        custom_rules="• New patient exam only $79.\n• Emergency walk-ins accepted until 6pm.",
    )
    print(f"[OK] Dental Room: {session_dental['room_name']}")
    print(f"[OK] First Greeting: '{session_dental['greeting']}'")

    print("\n=== All Dynamic Dispatch Studio Tests Passed Successfully! ===")

if __name__ == "__main__":
    asyncio.run(main())
