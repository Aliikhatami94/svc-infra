from __future__ import annotations

import json
from typing import Any, Optional

try:
    from redis import asyncio as redis
except Exception:  # pragma: no cover
    redis = None  # type: ignore


class RedisCache:
    def __init__(self, url: str, namespace: str = ""):
        if redis is None:  # pragma: no cover
            raise RuntimeError(
                "redis package not installed. Install 'redis>=5' to use RedisCache."
            )
        self._pool = redis.from_url(url, decode_responses=True)
        self._ns = (namespace + ":") if namespace else ""

    def _k(self, key: str) -> str:
        return self._ns + key

    async def get(self, key: str) -> Optional[Any]:
        val = await self._pool.get(self._k(key))
        return json.loads(val) if val else None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        await self._pool.set(self._k(key), json.dumps(value), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._pool.delete(self._k(key))

