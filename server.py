from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from app.database.base import init_db, close_db
from app.routes.webhook import router as webhook_router
from app.config.settings import settings
from app.services.cache_service import cache_service

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("🚀 Jeevo Health Platform starting...")
    logger.info(f"📱 WhatsApp webhook endpoint: /api/webhook")
    logger.info(f"🤖 AI Model: {'Groq ' + settings.GROQ_MODEL if settings.USE_GROQ else 'OpenAI ' + settings.OPENAI_MODEL}")

    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")

    try:
        await cache_service.connect()
        logger.info("✅ Redis cache initialized")
    except Exception as e:
        logger.warning(f"⚠️ Redis cache not available: {e}")

    yield

    logger.info("👋 Shutting down...")
    await cache_service.disconnect()
    await close_db()
    logger.info("✅ Database and Redis connections closed")

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan
)

app.include_router(webhook_router, prefix="/api")
# Also mount without a prefix so external senders posting to `/webhook` succeed
app.include_router(webhook_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Jeevo Health Platform API",
        "version": "2.0",
        "description": "Multilingual health assistant with environmental monitoring",
        "features": [
            "Multilingual support (10 Indian languages)",
            "Voice & image analysis",
            "Environmental health alerts",
            "Vaccine tracking & reminders",
            "Disease outbreak warnings"
        ]
    }

@app.get("/api")
async def api_root():
    return {
        "message": "Jeevo Health Platform API",
        "version": "2.0"
    }

@app.get("/api/health")
async def health_check():
    from datetime import datetime, timezone

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "postgresql",
            "cache": "redis",
            "whatsapp": "configured" if settings.WHATSAPP_ACCESS_TOKEN != "your_whatsapp_access_token_here" else "not_configured",
            "ai_model": settings.GROQ_MODEL if settings.USE_GROQ else settings.OPENAI_MODEL
        }
    }