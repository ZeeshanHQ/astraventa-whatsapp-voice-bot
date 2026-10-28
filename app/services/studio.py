import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from app.config import settings
from app.services.scraper import scrape_website_summary

logger = logging.getLogger("studio_service")

# ---------------------------------------------------------------------------
# Pre-built Industry Templates for Instant 5-Second Demos
# ---------------------------------------------------------------------------
INDUSTRY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "real_estate": {
        "label": "Real Estate Agency",
        "default_voice": "25679595-ec67-4228-97fb-0309993bdc71",
        "greeting": "Hi there! Thanks for calling {business_name}. Are you looking to buy, sell, or rent a property today?",
        "base_rules": (
            "You are the cheerful, highly knowledgeable voice receptionist for {business_name}, a top-tier real estate firm.\n"
            "Your goals:\n"
            "1. Identify if the caller is looking to BUY, SELL, or RENT.\n"
            "2. Ask for their preferred location and target budget.\n"
            "3. Offer to connect them with a licensed senior agent or schedule a private showing.\n"
            "Rules: Speak naturally in 1-2 conversational sentences. Never use bullet points or markdown. Never give fake legal or mortgage advice."
        ),
    },
    "dental_clinic": {
        "label": "Dental / Medical Clinic",
        "default_voice": "79a125e8-cd45-4c13-8a67-188112f4dd22",
        "greeting": "Hello! Thank you for calling {business_name}. Are you calling to book a routine cleaning, or are you experiencing any dental discomfort?",
        "base_rules": (
            "You are the warm, compassionate patient coordinator for {business_name}.\n"
            "Your goals:\n"
            "1. Determine whether the patient is calling for routine checkups, cosmetic treatments, or an urgent dental emergency.\n"
            "2. Offer appointment slots for this week (e.g., mornings or afternoons).\n"
            "3. Collect the patient's full name and confirm their best callback number.\n"
            "Rules: Keep answers brief, empathetic, and under 20 words. Never diagnose clinical symptoms over the phone."
        ),
    },
    "home_services": {
        "label": "Home Services (HVAC / Plumbing / Roofing)",
        "default_voice": "694f9389-aac1-45b6-b726-9d9369183238",
        "greeting": "Thanks for calling {business_name}! How can we help with your home heating, cooling, or plumbing today?",
        "base_rules": (
            "You are the responsive, friendly dispatcher for {business_name}.\n"
            "Your goals:\n"
            "1. Ask what service they need (e.g. AC not turning on, pipe leak, tune-up).\n"
            "2. Ask if this is an urgent emergency needing same-day service.\n"
            "3. Ask for their zip code or city to verify service coverage.\n"
            "Rules: Short, helpful responses. Sound like a helpful neighbor. Confirm technician arrival windows."
        ),
    },
    "law_firm": {
        "label": "Law Firm & Legal Intake",
        "default_voice": "a0e99841-438c-4a64-b679-ae501e7d6091",
        "greeting": "Hello, thank you for contacting {business_name}. How can our legal team assist you today?",
        "base_rules": (
            "You are the professional, discreet legal intake specialist for {business_name}.\n"
            "Your goals:\n"
            "1. Inquire briefly about the nature of the matter (e.g., personal injury, corporate, family law).\n"
            "2. Reassure the caller that all details are treated with strict confidentiality.\n"
            "3. Offer to schedule an initial consultation with one of the attorneys.\n"
            "Rules: Professional and polite. Remind the caller that this conversation is intake only and does not constitute formal legal counsel."
        ),
    },
    "tech_agency": {
        "label": "Astraventa / Tech & AI Agency",
        "default_voice": "25679595-ec67-4228-97fb-0309993bdc71",
        "greeting": "Hello! Thanks for reaching out to {business_name}. How can we assist with your AI automation, voice agents, or software engineering today?",
        "base_rules": (
            "You are the tech-savvy, professional AI voice receptionist for {business_name}, a specialized AI and automation agency.\n"
            "Your goals:\n"
            "1. Understand what project the caller is looking to automate (voice bots, web apps, enterprise integrations).\n"
            "2. Highlight our rapid prototyping and custom AI agent engineering.\n"
            "3. Offer to book a 15-minute technical walkthrough with our founding engineering team.\n"
            "Rules: Keep replies to 1-2 sharp, punchy sentences. Never speak markdown or raw URLs."
        ),
    },
}

# ---------------------------------------------------------------------------
# High-Fidelity Voice Catalog (Cartesia Sonic & Deepgram Aura)
# ---------------------------------------------------------------------------
VOICE_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "25679595-ec67-4228-97fb-0309993bdc71",
        "name": "Sarah (Warm & Conversational)",
        "gender": "female",
        "provider": "cartesia",
        "accent": "US American",
        "description": "Ideal for patient coordination, customer support, and friendly consultations.",
    },
    {
        "id": "694f9389-aac1-45b6-b726-9d9369183238",
        "name": "Michael (Direct & Confident)",
        "gender": "male",
        "provider": "cartesia",
        "accent": "US American",
        "description": "Punchy, authoritative, perfect for dispatch, sales discovery, and real estate.",
    },
    {
        "id": "79a125e8-cd45-4c13-8a67-188112f4dd22",
        "name": "Emma (Polished & Professional)",
        "gender": "female",
        "provider": "cartesia",
        "accent": "British",
        "description": "Sophisticated, calming tone for luxury real estate and professional clinics.",
    },
    {
        "id": "a0e99841-438c-4a64-b679-ae501e7d6091",
        "name": "David (Warm & Deep)",
        "gender": "male",
        "provider": "cartesia",
        "accent": "US American",
        "description": "Deep resonant voice for executive intake, financial advisory, and legal firms.",
    },
    {
        "id": "aura-asteria-en",
        "name": "Asteria (Deepgram Natural)",
        "gender": "female",
        "provider": "deepgram",
        "accent": "US American",
        "description": "Reliable, ultra-fast female voice built directly into Deepgram Aura.",
    },
    {
        "id": "aura-orion-en",
        "name": "Orion (Deepgram Confident)",
        "gender": "male",
        "provider": "deepgram",
        "accent": "US American",
        "description": "Clear male speaker with high intelligibility for telephone calls.",
    },
]


class StudioService:
    """
    Orchestrates dynamic tenant prompt synthesis, fast website scraping,
    and LiveKit WebRTC session minting for instant in-meeting demonstrations.
    """

    @staticmethod
    def get_templates() -> Dict[str, Dict[str, Any]]:
        return INDUSTRY_TEMPLATES

    @staticmethod
    def get_voices() -> List[Dict[str, Any]]:
        return VOICE_CATALOG

    @staticmethod
    async def build_dynamic_prompt(
        business_name: str,
        industry: str = "tech_agency",
        website_url: Optional[str] = None,
        custom_rules: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Synthesizes a tailored, high-converting phone system prompt in under 2 seconds.
        """
        template = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["tech_agency"])
        base_rules = template["base_rules"].format(business_name=business_name)
        greeting = template["greeting"].format(business_name=business_name)

        # Scrape website if provided
        scraped_context = ""
        if website_url and website_url.strip():
            scraped = await scrape_website_summary(website_url.strip())
            if scraped.get("success") and scraped.get("summary"):
                scraped_context = f"\n\nContext from client website:\n{scraped['summary']}"

        # Additional custom bullet rules
        rules_context = ""
        if custom_rules and custom_rules.strip():
            rules_context = f"\n\nClient-Specific Directives & FAQs:\n{custom_rules.strip()}"

        strict_phone_guidelines = (
            "\n\nSTRICT VOICE CONVERSATION PROTOCOL:\n"
            "1. You are on a live phone/audio call. Speak in ONE or TWO short, conversational sentences only (under 25 words per turn).\n"
            "2. Never use bullet points, asterisks, formatting symbols, or markdown.\n"
            "3. Never speak website URLs or email addresses character-by-character. Suggest visiting the company website or booking on our calendar instead.\n"
            "4. Be attentive, warm, and steer the conversation proactively to help the client.\n"
            "5. If the caller asks something outside your knowledge, politely offer to have a specialist follow up with them."
        )

        final_system_prompt = base_rules + scraped_context + rules_context + strict_phone_guidelines
        return {
            "system_prompt": final_system_prompt,
            "greeting": greeting,
        }

    @staticmethod
    def create_livekit_token(
        room_name: str,
        participant_identity: str,
        participant_name: str = "Client Prospect",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Mints a LiveKit WebRTC AccessToken with permissions to join the demo room.
        """
        if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
            # Provide development fallback token representation if keys are not yet added
            logger.warning("LIVEKIT_API_KEY / SECRET not configured. Token generation will fail if connecting to live cluster.")
            return ""

        try:
            from livekit.api import AccessToken, VideoGrants

            token = AccessToken(
                api_key=settings.LIVEKIT_API_KEY,
                api_secret=settings.LIVEKIT_API_SECRET,
            )
            token.with_identity(participant_identity)
            token.with_name(participant_name)

            if metadata:
                token.with_metadata(json.dumps(metadata))

            grants = VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
            token.with_grants(grants)
            return token.to_jwt()

        except Exception as exc:
            logger.error(f"Error generating LiveKit AccessToken: {exc}", exc_info=True)
            return ""

    @staticmethod
    async def create_demo_session(
        business_name: str,
        industry: str = "tech_agency",
        website_url: Optional[str] = None,
        custom_rules: Optional[str] = None,
        voice_id: Optional[str] = None,
        caller_phone: Optional[str] = None,
        transfer_phone_number: Optional[str] = None,
        calendar_link: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main Dynamic Dispatch Entrypoint:
        1. Synthesizes tailored system prompt & initial greeting.
        2. Assigns high-fidelity voice.
        3. Persists tenant and agent configuration into Supabase database.
        4. Formulates room name & dynamic payload metadata.
        5. Mints in-browser WebRTC token.
        """
        prompt_data = await StudioService.build_dynamic_prompt(
            business_name=business_name,
            industry=industry,
            website_url=website_url,
            custom_rules=custom_rules,
        )

        selected_voice = voice_id
        if not selected_voice:
            template = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["tech_agency"])
            selected_voice = template["default_voice"]

        # Formulate unique room name for this prospect session
        session_id = str(uuid.uuid4())[:8]
        safe_biz = "".join(c for c in business_name.lower().replace(" ", "-") if c.isalnum() or c == "-")[:16]
        room_name = f"demo-{safe_biz}-{session_id}"

        # Resolve contact settings
        resolved_transfer_number = (
            transfer_phone_number
            or settings.FORWARDING_TARGET
            or "+19255040101"
        )
        resolved_calendar_link = (
            calendar_link
            or "https://calendly.com/astraventaai/15-min-technical-walkthrough-astraventa"
        )

        # -------------------------------------------------------------------
        # Persist Tenant & Agent Configuration to Supabase (Graceful Fallback)
        # -------------------------------------------------------------------
        saved_tenant_id = tenant_id
        try:
            from app.services.db import get_supabase_client
            supabase = get_supabase_client()
            if supabase:
                # 1. Upsert / Ensure Tenant
                if not saved_tenant_id:
                    slug = safe_biz
                    existing_t = supabase.table("tenants").select("id").eq("slug", slug).limit(1).execute()
                    if existing_t.data and len(existing_t.data) > 0:
                        saved_tenant_id = existing_t.data[0]["id"]
                        supabase.table("tenants").update({
                            "name": business_name,
                            "industry": industry,
                            "website_url": website_url or "",
                            "phone_number": resolved_transfer_number,
                            "updated_at": "now()",
                        }).eq("id", saved_tenant_id).execute()
                    else:
                        new_t = supabase.table("tenants").insert({
                            "name": business_name,
                            "slug": slug,
                            "industry": industry,
                            "website_url": website_url or "",
                            "phone_number": resolved_transfer_number,
                        }).execute()
                        if new_t.data and len(new_t.data) > 0:
                            saved_tenant_id = new_t.data[0]["id"]

                # 2. Upsert Agent Configuration
                if saved_tenant_id:
                    existing_cfg = supabase.table("agent_configs").select("id").eq("tenant_id", saved_tenant_id).limit(1).execute()
                    cfg_payload = {
                        "tenant_id": saved_tenant_id,
                        "name": f"{business_name} AI Voice Agent",
                        "system_prompt": prompt_data["system_prompt"],
                        "first_message": prompt_data["greeting"],
                        "voice_id": selected_voice,
                        "voice_provider": "cartesia" if not selected_voice.startswith("aura-") else "deepgram",
                        "llm_model": "llama-3.3-70b-versatile",
                        "stt_model": "nova-3",
                        "rules": [custom_rules] if custom_rules else [],
                        "is_active": True,
                        "updated_at": "now()",
                    }
                    if existing_cfg.data and len(existing_cfg.data) > 0:
                        cfg_id = existing_cfg.data[0]["id"]
                        supabase.table("agent_configs").update(cfg_payload).eq("id", cfg_id).execute()
                    else:
                        supabase.table("agent_configs").insert(cfg_payload).execute()

                # 3. Log Call Session
                supabase.table("demo_sessions").insert({
                    "tenant_id": saved_tenant_id,
                    "room_name": room_name,
                    "session_type": "sip_phone" if caller_phone else "webrtc_browser",
                    "destination_phone": caller_phone or "",
                    "status": "initiated",
                }).execute()
                logger.info(f"Persisted tenant [{business_name}] & agent configuration in Supabase (ID: {saved_tenant_id})")
        except Exception as db_exc:
            logger.warning(f"Database persistence fallback: Could not save tenant to Supabase: {db_exc}")

        # Metadata payload that the Universal LiveKit Worker will read instantly
        agent_metadata = {
            "tenant_id": str(saved_tenant_id) if saved_tenant_id else "",
            "business_name": business_name,
            "system_prompt": prompt_data["system_prompt"],
            "first_message": prompt_data["greeting"],
            "voice_id": selected_voice,
            "industry": industry,
            "session_id": session_id,
            "transfer_phone_number": resolved_transfer_number,
            "calendar_link": resolved_calendar_link,
        }

        # Generate Browser WebRTC Token
        browser_token = StudioService.create_livekit_token(
            room_name=room_name,
            participant_identity=f"client-{session_id}",
            participant_name=f"{business_name} Guest",
            metadata=agent_metadata,
        )

        return {
            "success": True,
            "room_name": room_name,
            "session_id": session_id,
            "tenant_id": saved_tenant_id,
            "livekit_url": settings.LIVEKIT_URL or "wss://your-livekit-server.com",
            "token": browser_token,
            "metadata": agent_metadata,
            "system_prompt_preview": prompt_data["system_prompt"][:350] + "...",
            "greeting": prompt_data["greeting"],
            "voice_id": selected_voice,
            "transfer_phone_number": resolved_transfer_number,
            "calendar_link": resolved_calendar_link,
        }

    @staticmethod
    async def trigger_sip_outbound_call(
        to_phone: str,
        business_name: str,
        industry: str = "tech_agency",
        website_url: Optional[str] = None,
        custom_rules: Optional[str] = None,
        voice_id: Optional[str] = None,
        transfer_phone_number: Optional[str] = None,
        calendar_link: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dials prospect's real phone line via LiveKit SIP + Telnyx Trunking:
        - Creates a dynamic LiveKit room with the prospect's metadata.
        - Issues SIP call dispatch to ring their mobile phone live.
        """
        session = await StudioService.create_demo_session(
            business_name=business_name,
            industry=industry,
            website_url=website_url,
            custom_rules=custom_rules,
            voice_id=voice_id,
            caller_phone=to_phone,
            transfer_phone_number=transfer_phone_number,
            calendar_link=calendar_link,
            tenant_id=tenant_id,
        )

        room_name = session["room_name"]
        metadata = session["metadata"]

        # Check for LiveKit API & SIP trunk
        if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_SIP_TRUNK_ID:
            logger.warning("LIVEKIT_SIP_TRUNK_ID or API_KEY not set. Outbound SIP simulated.")
            return {
                "success": True,
                "mode": "simulated",
                "message": f"SIP outbound call simulated for {to_phone} (Trunk ID pending in .env).",
                "session": session,
            }

        try:
            from livekit.api import LiveKitAPI, CreateSIPParticipantRequest

            lk_api = LiveKitAPI(
                url=settings.LIVEKIT_URL,
                api_key=settings.LIVEKIT_API_KEY,
                api_secret=settings.LIVEKIT_API_SECRET,
            )

            req = CreateSIPParticipantRequest(
                sip_trunk_id=settings.LIVEKIT_SIP_TRUNK_ID,
                sip_call_to=to_phone,
                room_name=room_name,
                participant_identity=f"phone-{to_phone}",
                participant_name=f"Caller ({to_phone})",
                participant_metadata=json.dumps(metadata),
            )

            res = await lk_api.sip.create_sip_participant(req)
            await lk_api.aclose()

            return {
                "success": True,
                "mode": "live",
                "participant_id": res.participant_id,
                "room_name": room_name,
                "message": f"Dialing {to_phone} via LiveKit SIP trunk...",
                "session": session,
            }

        except Exception as exc:
            logger.error(f"Failed to initiate LiveKit SIP outbound call: {exc}", exc_info=True)
            return {
                "success": False,
                "error": str(exc),
                "session": session,
            }


studio_service = StudioService()
