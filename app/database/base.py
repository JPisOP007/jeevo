from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config.settings import settings
import asyncio
import logging

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def get_db():

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Compatibility alias for older imports expecting `get_async_db`
get_async_db = get_db

async def init_db(max_retries: int = 10, retry_delay: float = 2.0):

    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables initialized successfully")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⏳ Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                logger.info(f"   Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"❌ Database initialization failed after {max_retries} attempts: {e}")
                raise
    return False

async def close_db():

    await engine.dispose()