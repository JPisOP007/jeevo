import redis.asyncio as redis
import json
from typing import Optional, Any
from datetime import timedelta
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis cache service for session management and caching"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = await redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Redis connected successfully")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis disconnected")
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set a value in cache
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            expire: Expiration time in seconds (default from settings)
        """
        try:
            if expire is None:
                expire = settings.REDIS_TTL
            
            # Serialize value to JSON
            serialized_value = json.dumps(value)
            
            await self.redis_client.setex(
                key,
                expire,
                serialized_value
            )
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache
        
        Args:
            key: Cache key
        
        Returns:
            Cached value (JSON deserialized) or None
        """
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {e}")
            return False
    
    async def set_session(
        self,
        phone_number: str,
        session_data: dict,
        expire_minutes: Optional[int] = None
    ) -> bool:
        """
        Set user session data
        
        Args:
            phone_number: User's phone number
            session_data: Session data dictionary
            expire_minutes: Session expiration in minutes
        """
        key = f"session:{phone_number}"
        expire_seconds = (expire_minutes or settings.SESSION_EXPIRE_MINUTES) * 60
        return await self.set(key, session_data, expire_seconds)
    
    async def get_session(self, phone_number: str) -> Optional[dict]:
        """Get user session data"""
        key = f"session:{phone_number}"
        return await self.get(key)
    
    async def delete_session(self, phone_number: str) -> bool:
        """Delete user session"""
        key = f"session:{phone_number}"
        return await self.delete(key)
    
    async def set_user_context(
        self,
        phone_number: str,
        context: dict
    ) -> bool:
        """Set conversation context for a user"""
        key = f"context:{phone_number}"
        return await self.set(key, context, expire=1800)  # 30 minutes
    
    async def get_user_context(self, phone_number: str) -> Optional[dict]:
        """Get conversation context for a user"""
        key = f"context:{phone_number}"
        return await self.get(key)
    
    async def cache_risk_level(
        self,
        pincode: str,
        risk_data: dict
    ) -> bool:
        """Cache local risk level data"""
        key = f"risk:{pincode}"
        return await self.set(key, risk_data, expire=3600)  # 1 hour
    
    async def get_cached_risk_level(self, pincode: str) -> Optional[dict]:
        """Get cached risk level data"""
        key = f"risk:{pincode}"
        return await self.get(key)
    
    async def increment_counter(self, key: str) -> int:
        """Increment a counter"""
        try:
            return await self.redis_client.incr(key)
        except Exception as e:
            logger.error(f"Error incrementing counter {key}: {e}")
            return 0
    
    async def get_stats(self) -> dict:
        """Get Redis stats"""
        try:
            info = await self.redis_client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "Unknown"),
                "total_keys": await self.redis_client.dbsize(),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {"connected": False, "error": str(e)}


# Create global cache service instance
cache_service = CacheService()