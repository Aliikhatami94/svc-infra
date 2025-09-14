from __future__ import annotations

from redis.asyncio import Redis


class RedisLock:
    def __init__(self, redis: Redis, key: str, ttl: int = 30):
        self.redis = redis
        self.key = key
        self.ttl = ttl
        self.token: bytes | None = None

    async def __aenter__(self):
        # Spin a little; simple & good enough for stampede avoidance
        for _ in range(50):
            if await self.redis.set(self.key, b"1", nx=True, ex=self.ttl):
                self.token = b"1"
                return self
            # brief backoff
            await self.redis.wait(1, timeout=0.01)  # cheap yield
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self.redis.delete(self.key)
        except Exception:
            pass
