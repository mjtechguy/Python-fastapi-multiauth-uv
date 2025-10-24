"""Caching service for Redis-based caching."""

import json
from collections.abc import Callable
from functools import wraps
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings


class CacheService:
    """Redis-based caching service."""

    def __init__(self):
        """Initialize cache service."""
        self.redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if not self.redis:
            self.redis = await aioredis.from_url(
                str(settings.REDIS_URL).replace(f"/{settings.REDIS_CACHE_DB}", f"/{settings.REDIS_CACHE_DB}"),
                encoding="utf-8",
                decode_responses=True,
            )

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not self.redis:
            await self.connect()

        value = await self.redis.get(key)  # type: ignore
        if value:
            return json.loads(value)
        return None

    async def set(
        self, key: str, value: Any, expire: int | None = None
    ) -> None:
        """Set value in cache with optional expiration."""
        if not self.redis:
            await self.connect()

        serialized = json.dumps(value)
        if expire:
            await self.redis.setex(key, expire, serialized)  # type: ignore
        else:
            await self.redis.set(key, serialized)  # type: ignore

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        if not self.redis:
            await self.connect()

        await self.redis.delete(key)  # type: ignore

    async def clear_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern."""
        if not self.redis:
            await self.connect()

        keys = await self.redis.keys(pattern)  # type: ignore
        if keys:
            await self.redis.delete(*keys)  # type: ignore

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis:
            await self.connect()

        return bool(await self.redis.exists(key))  # type: ignore


# Global cache instance
cache = CacheService()


def cached(expire: int = 300, key_prefix: str = ""):
    """
    Decorator for caching function results.

    Args:
        expire: Expiration time in seconds (default 5 minutes)
        key_prefix: Prefix for cache keys

    Example:
        @cached(expire=600, key_prefix="user")
        async def get_user(user_id: str):
            return await db.get_user(user_id)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{args!s}:{kwargs!s}"

            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, expire=expire)

            return result

        return wrapper

    return decorator
