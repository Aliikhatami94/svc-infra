from __future__ import annotations

# Backward-compat shim for RedisCache and @cache decorator
from .cache.redis import RedisCache as RedisCache  # noqa: F401


def cache(ttl: int = 300):
    """Simple JSON cache decorator expecting `self.cache` to implement BaseCache."""
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
