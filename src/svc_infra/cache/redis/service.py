from __future__ import annotations

from redis.asyncio import Redis

from svc_infra.cache.service import CacheBackend


class RedisBackend(CacheBackend):
    def __init__(self, redis: Redis):
        self.r = redis

    async def get(self, key: str) -> bytes | None:
        return await self.r.get(key)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        return bool(await self.r.set(key, value, ex=ttl))

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return int(await self.r.delete(*keys))

    async def mget(self, *keys: str) -> list[bytes | None]:
        if not keys:
            return []
        vals = await self.r.mget(list(keys))
        return list(vals or [])

    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        v = await self.r.incrby(key, amount)
        if ttl:
            await self.r.expire(key, ttl)
        return int(v)
