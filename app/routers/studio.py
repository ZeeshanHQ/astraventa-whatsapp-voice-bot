import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.studio import studio_service
from app.services.scraper import scrape_website_summary

logger = logging.getLogger("studio_router")
router = APIRouter(prefix="/api/studio", tags=["Voice AI Studio"])


# ---------------------------------------------------------------------------
# Request & Response Models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    business_name: str = Field(..., example="Apex Smile Dental")
    industry: str = Field("dental_clinic", example="dental_clinic")
    website_url: Optional[str] = Field(None, example="https://apexsmiles.com")
    custom_rules: Optional[str] = Field(None, example="1. Offer 20% off for new patients.\n2. Closed on Sundays.")
    voice_id: Optional[str] = Field(None, example="79a125e8-cd45-4c13-8a67-188112f4dd22")
    transfer_phone_number: Optional[str] = Field(None, example="+19255040101")
    calendar_link: Optional[str] = Field(None, example="https://calendly.com/astraventaai/15-min-technical-walkthrough-astraventa")
    tenant_id: Optional[str] = Field(None, example=None)


class OutboundCallRequest(BaseModel):
    to_phone: str = Field(..., example="+19255040101")
    business_name: str = Field(..., example="Premier Luxury Realty")
    industry: str = Field("real_estate", example="real_estate")
    website_url: Optional[str] = None
    custom_rules: Optional[str] = None
    voice_id: Optional[str] = None
    transfer_phone_number: Optional[str] = None
    calendar_link: Optional[str] = None
    tenant_id: Optional[str] = None


class ScrapeRequest(BaseModel):
    url: str = Field(..., example="https://example.com")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/templates")
async def get_templates():
    """Returns pre-built industry templates for instant 5-second demos."""
    return {"templates": studio_service.get_templates()}


@router.get("/voices")
async def get_voices():
    """Returns curated voice catalog with Cartesia Sonic & Deepgram Aura."""
    return {"voices": studio_service.get_voices()}


@router.post("/scrape")
async def scrape_url_endpoint(req: ScrapeRequest):
    """
    Rapidly scrapes business context from a prospect's URL in under 2 seconds.
    """
    res = await scrape_website_summary(req.url)
    return res


@router.post("/create-session")
async def create_demo_session_endpoint(req: CreateSessionRequest):
    """
    Generates dynamic prompt + metadata, mints LiveKit token,
    and returns connection details for in-browser live demo.
    """
    try:
        session = await studio_service.create_demo_session(
            business_name=req.business_name,
            industry=req.industry,
            website_url=req.website_url,
            custom_rules=req.custom_rules,
            voice_id=req.voice_id,
            transfer_phone_number=req.transfer_phone_number,
            calendar_link=req.calendar_link,
            tenant_id=req.tenant_id,
        )
        return session
    except Exception as exc:
        logger.error(f"Error in create_demo_session_endpoint: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/outbound-call")
async def outbound_call_endpoint(req: OutboundCallRequest):
    """
    Dials prospect's mobile phone via LiveKit SIP trunk with the custom agent.
    """
    try:
        res = await studio_service.trigger_sip_outbound_call(
            to_phone=req.to_phone,
            business_name=req.business_name,
            industry=req.industry,
            website_url=req.website_url,
            custom_rules=req.custom_rules,
            voice_id=req.voice_id,
            transfer_phone_number=req.transfer_phone_number,
            calendar_link=req.calendar_link,
            tenant_id=req.tenant_id,
        )
        return res
    except Exception as exc:
        logger.error(f"Error in outbound_call_endpoint: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
