from __future__ import annotations

import hashlib
import inspect
import json
from typing import Any, Awaitable, Callable

from svc_infra.cache.redis.lock import (  # used only if backend is Redis; safe no-op for others
    RedisLock,
)
from svc_infra.cache.service import CacheService


def _hash_args(*args, **kwargs) -> str:
    try:
        raw = json.dumps([args, kwargs], default=str, sort_keys=True, separators=(",", ":"))
    except Exception:
        raw = repr((args, kwargs))
    return hashlib.sha1(raw.encode()).hexdigest()


def cacheable(prefix: str, ttl: int | None = None):
    """Cache the result of an async function using args as cache key."""

    def wrap(fn: Callable[..., Awaitable[Any]]):
        if not inspect.iscoroutinefunction(fn):
            raise TypeError("cacheable expects an async function")

        async def inner(cache: CacheService, *args, **kwargs):
            k = cache.key(prefix, _hash_args(*args, **kwargs))
            hit = await cache.backend.get(k)
            if hit is not None:
                from .codec import loads

                return loads(hit)

            # Stampede protection if backend is Redis
            rds = getattr(getattr(cache.backend, "r", None), "set", None)
            if rds:
                from redis.asyncio import Redis

                redis_client: Redis = cache.backend.r  # type: ignore[attr-defined]
                async with RedisLock(redis_client, key=k + ":lock", ttl=10):
                    again = await cache.backend.get(k)
                    if again is not None:
                        from .codec import loads

                        return loads(again)
                    res = await fn(*args, **kwargs)
                    from .codec import dumps

                    await cache.backend.set(k, dumps(res), ttl or cache.default_ttl)
                    return res

            # Fallback (no lock)
            res = await fn(*args, **kwargs)
            from .codec import dumps

            await cache.backend.set(k, dumps(res), ttl or cache.default_ttl)
            return res

        return inner

    return wrap
