from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

from cashews import cache as _cache

DEFAULT_PREFIX = os.getenv("CACHE_PREFIX", "svc")
DEFAULT_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_VERSION = os.getenv("CACHE_VERSION", "v1")  # bump to invalidate whole namespace


def _alias(prefix: Optional[str] = None, version: Optional[str] = None) -> str:
    p = prefix or DEFAULT_PREFIX
    v = version or CACHE_VERSION
    return f"{p}:{v}"


def setup_cache(
    url: Optional[str] = None,
    *,
    prefix: Optional[str] = None,
    version: Optional[str] = None,
) -> None:
    _cache.setup(url or DEFAULT_URL, client_side=None)
    _cache.set_alias(_alias(prefix, version))


async def startup_check(retries: int = 3, delay_seconds: float = 0.5) -> None:
    """
    Optional readiness probe: round-trip set/get. Async-safe (no blocking).
    """
    key = f"{_cache.get_alias()}:_startup:{int(time.time())}"
    for attempt in range(1, retries + 1):
        try:
            await _cache.set(key, "ok", expire=5)
            v = await _cache.get(key)
            if v == "ok":
                return
        except Exception:
            if attempt == retries:
                raise
        # IMPORTANT: yield the event loop
        await asyncio.sleep(delay_seconds)


async def shutdown_cache() -> None:
    await _cache.close()


def instance():
    return _cache
