from __future__ import annotations

import json
from typing import Any, Optional

# Optional dependency: redis>=5 provides asyncio support under redis.asyncio
# This module is not exported by default; import it only if you install redis.
try:
    from redis import asyncio as redis
except Exception:  # pragma: no cover - optional import
    redis = None  # type: ignore


class RedisCache:
    def __init__(self, url: str):
        if redis is None:  # pragma: no cover
            raise RuntimeError(
                "redis package not installed. Install 'redis>=5' to use RedisCache."
            )
        self._pool = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        val = await self._pool.get(key)
        return json.loads(val) if val else None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        await self._pool.set(key, json.dumps(value), ex=ttl)


def cache(ttl: int = 300):
    def deco(fn):
        async def wrap(self, key: str, *a, **k):
            val = await self.cache.get(key)
            if val is not None:
                return val
            val = await fn(self, key, *a, **k)
            await self.cache.set(key, val, ttl=ttl)
            return val
        return wrap
    return deco
