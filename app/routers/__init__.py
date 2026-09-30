from app.routers.webhook import router as webhook_router
from app.routers.ai_test import router as ai_test_router
from app.routers.voice import router as voice_router
from app.routers.sms import router as sms_router
from app.routers.contacts import router as contacts_router

__all__ = ["webhook_router", "ai_test_router", "voice_router", "sms_router", "contacts_router"]
