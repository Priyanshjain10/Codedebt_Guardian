"""
Redis cache service for CodeDebt Guardian.
Provides simple get/set/delete with TTL and JSON serialization.
"""

import json
import logging
from typing import Any, Optional
import redis as redis_lib
from config import settings

logger = logging.getLogger(__name__)

_redis: Optional[redis_lib.Redis] = None


def get_redis() -> Optional[redis_lib.Redis]:
    """Lazy Redis client — returns None if unavailable."""
    global _redis
    if _redis is None:
        try:
            _redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
            _redis.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable for cache: {e}")
            _redis = None
    return _redis


def cache_get(key: str) -> Optional[Any]:
    r = get_redis()
    if not r:
        return None
    try:
        val = r.get(key)
        return json.loads(val) if val else None
    except Exception as e:
        logger.warning(f"Cache get failed for {key}: {e}")
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as e:
        logger.warning(f"Cache set failed for {key}: {e}")
        return False


def cache_delete(key: str) -> bool:
    r = get_redis()
    if not r:
        return False
    try:
        r.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Cache delete failed for {key}: {e}")
        return False


def cache_invalidate_prefix(prefix: str) -> int:
    """Delete all keys matching a prefix pattern."""
    r = get_redis()
    if not r:
        return 0
    try:
        keys = r.keys(f"{prefix}*")
        if keys:
            r.delete(*keys)
        return len(keys)
    except Exception as e:
        logger.warning(f"Cache invalidate failed for {prefix}: {e}")
        return 0
