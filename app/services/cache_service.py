"""Cache service for Redis operations."""
import logging
from typing import Any, Optional
import json
import redis
from functools import wraps

from app.utils.exceptions import CacheError


logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service with convenience methods.
    """
    
    def __init__(self, redis_url: str):
        """
        Initialize cache service.
        
        Args:
            redis_url: Redis connection URL
        """
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {str(e)}. Caching disabled.")
            self.redis_client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get failed for key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        if not self.redis_client:
            return
        
        try:
            serialized = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"Cache set failed for key {key}: {str(e)}")
    
    def delete(self, key: str):
        """Delete key from cache."""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Cache delete failed for key {key}: {str(e)}")
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis_client:
            return False
        
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists check failed for key {key}: {str(e)}")
            return False
    
    def keys(self, pattern: str = "*"):
        """Get all keys matching pattern."""
        if not self.redis_client:
            return []
        
        try:
            return self.redis_client.keys(pattern)
        except Exception as e:
            logger.error(f"Cache keys fetch failed for pattern {pattern}: {str(e)}")
            return []
    
    def flush(self):
        """Clear all cache."""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.flushdb()
            logger.info("Cache flushed")
        except Exception as e:
            logger.error(f"Cache flush failed: {str(e)}")
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        if not self.redis_client:
            return 0
        
        try:
            return self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment failed for key {key}: {str(e)}")
            return 0
    
    def get_hash(self, key: str) -> dict:
        """Get hash value."""
        if not self.redis_client:
            return {}
        
        try:
            return self.redis_client.hgetall(key)
        except Exception as e:
            logger.error(f"Cache hash get failed for key {key}: {str(e)}")
            return {}
    
    def set_hash(self, key: str, mapping: dict):
        """Set hash value."""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.hset(key, mapping=mapping)
        except Exception as e:
            logger.error(f"Cache hash set failed for key {key}: {str(e)}")


def cached(ttl=3600, key_prefix=""):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache from first argument (should be self with cache attribute)
            if args and hasattr(args[0], 'cache'):
                cache = args[0].cache
                
                # Generate cache key
                import hashlib
                key_data = f"{key_prefix}:{func.__name__}:{args[1:]}:{sorted(kwargs.items())}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()
                
                # Try to get from cache
                cached_value = cache.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Cache result
                cache.set(cache_key, result, ttl=ttl)
                
                return result
            
            # No cache available, execute normally
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
