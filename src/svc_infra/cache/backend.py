from __future__ import annotations

import os

from cashews import cache as _cache

_DEFAULT_PREFIX = os.getenv("CACHE_PREFIX", "svc")


def setup_cache(url: str | None = None, *, prefix: str | None = None) -> None:
    url = url or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
    _cache.setup(url)  # lazy connect
    _cache.set_alias(prefix or _DEFAULT_PREFIX)


async def close_cache() -> None:
    await _cache.close()  # safe no-op


def instance():
    return _cache
