"""
Memory Bank - In-memory key-value store with TTL support.
Provides shared memory across agents for caching and context management.
"""

import time
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MemoryEntry:
    def __init__(self, value: Any, ttl_seconds: Optional[int] = None):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl_seconds

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl


class MemoryBank:
    """
    Shared in-memory store for agent communication and caching.

    Features:
    - TTL-based expiry
    - Namespace support
    - Access statistics
    """

    def __init__(self):
        self._store: Dict[str, MemoryEntry] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value, returning None if missing or expired."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired():
            del self._store[key]
            self._misses += 1
            logger.debug(f"Cache expired: {key}")
            return None
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store a value with optional TTL."""
        self._store[key] = MemoryEntry(value, ttl_seconds)
        logger.debug(f"Cached: {key} (TTL: {ttl_seconds}s)")

    def delete(self, key: str) -> None:
        """Delete a key from the store."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all entries."""
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        """Return memory bank statistics."""
        total = self._hits + self._misses
        return {
            "total_keys": len(self._store),
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0,
        }
