from __future__ import annotations

import asyncio
from typing import Optional

from redis.asyncio import Redis

from svc_infra.cache.settings import CacheSettings

from .settings import RedisPoolConfig

_redis: Optional[Redis] = None
_lock = asyncio.Lock()


async def init_redis(url: str | None = None, *, pool: RedisPoolConfig | None = None) -> Redis:
    global _redis
    async with _lock:
        if _redis:
            return _redis
        settings = CacheSettings()
        url = url or settings.resolved_url
        pool = pool or RedisPoolConfig()
        _redis = Redis.from_url(
            url,
            encoding=None,  # bytes in/out
            decode_responses=False,
            max_connections=pool.max_connections,
            socket_timeout=pool.socket_timeout,
            socket_connect_timeout=pool.socket_connect_timeout,
        )
        # quick ping to fail fast
        await _redis.ping()
        return _redis


async def acquire_redis() -> Redis:
    if _redis is None:
        await init_redis()
    assert _redis is not None
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
