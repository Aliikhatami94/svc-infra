from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from typing import Any, Awaitable, Callable

from svc_infra.cache.redis.lock import RedisLock
from svc_infra.cache.service import CacheService


def _hash_args(*args, **kwargs) -> str:
    try:
        raw = json.dumps([args, kwargs], default=str, sort_keys=True, separators=(",", ":"))
    except Exception:
        raw = repr((args, kwargs))
    return hashlib.sha1(raw.encode()).hexdigest()


def cacheable(prefix: str, ttl: int | None = None):
    def wrap(fn: Callable[..., Awaitable[Any]]):
        if not inspect.iscoroutinefunction(fn):
            raise TypeError("cacheable expects an async function")

        async def inner(cache: CacheService, *args, **kwargs):
            from .codec import dumps, loads

            k = cache.key(prefix, _hash_args(*args, **kwargs))

            hit = await cache.backend.get(k)
            if hit is not None:
                return loads(hit)

            # With Redis, try lock → compute → set.
            redis_client = getattr(getattr(cache.backend, "r", None), "ping", None)
            if redis_client:
                redis = cache.backend.r  # type: ignore
                async with RedisLock(redis, key=k + ":lock", ttl=10) as lk:
                    if lk.acquired:
                        again = await cache.backend.get(k)
                        if again is not None:
                            return loads(again)
                        res = await fn(*args, **kwargs)
                        await cache.backend.set(k, dumps(res), ttl or cache.default_ttl)
                        return res
                    else:
                        # Didn’t acquire — poll briefly for someone else’s result
                        for _ in range(20):
                            again = await cache.backend.get(k)
                            if again is not None:
                                return loads(again)
                            await asyncio.sleep(0.025)
                        # Still cold; compute (rare)
                        res = await fn(*args, **kwargs)
                        await cache.backend.set(k, dumps(res), ttl or cache.default_ttl)
                        return res

            # Non-Redis backends: compute + set
            res = await fn(*args, **kwargs)
            await cache.backend.set(k, dumps(res), ttl or cache.default_ttl)
            return res

        return inner

    return wrap
