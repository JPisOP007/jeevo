from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from app.config.settings import settings
from app.routes import webhook
from app.database.base import init_db, close_db
from app.services.cache_service import cache_service

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    # Startup
    logger.info("=" * 50)
    logger.info(f"🚀 Starting {settings.APP_NAME}")
    logger.info(f"📱 WhatsApp Phone Number ID: {settings.WHATSAPP_PHONE_NUMBER_ID}")
    logger.info(f"🔧 Debug Mode: {settings.DEBUG}")
    logger.info("=" * 50)
    
    # Initialize database
    try:
        logger.info("📊 Initializing PostgreSQL database...")
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Connect to Redis
    try:
        logger.info("🔴 Connecting to Redis...")
        await cache_service.connect()
        redis_stats = await cache_service.get_stats()
        logger.info(f"✅ Redis connected - Keys: {redis_stats.get('total_keys', 0)}")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise
    
    logger.info("=" * 50)
    logger.info("✅ All services started successfully!")
    logger.info("=" * 50)
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down services...")
    
    # Close Redis
    await cache_service.disconnect()
    logger.info("✅ Redis disconnected")
    
    # Close database
    await close_db()
    logger.info("✅ Database closed")
    
    logger.info("👋 Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="WhatsApp-based multilingual health assistant for rural India",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(webhook.router, tags=["WhatsApp Webhook"])


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "app": settings.APP_NAME,
        "status": "running",
        "message": "Jeevo WhatsApp Health Platform API is active"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    # Get Redis stats
    redis_stats = await cache_service.get_stats()
    
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "database": "connected",
        "redis": redis_stats
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )