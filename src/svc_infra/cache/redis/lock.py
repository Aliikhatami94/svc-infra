from __future__ import annotations

import asyncio

from redis.asyncio import Redis


class RedisLock:
    def __init__(self, redis: Redis, key: str, ttl: int = 30):
        self.redis = redis
        self.key = key
        self.ttl = ttl
        self.acquired = False

    async def __aenter__(self):
        for _ in range(50):
            if await self.redis.set(self.key, b"1", nx=True, ex=self.ttl):
                self.acquired = True
                return self
            await asyncio.sleep(0.02)  # tiny backoff
        return self  # not acquired

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self.acquired:
                await self.redis.delete(self.key)
        except Exception:
            pass
