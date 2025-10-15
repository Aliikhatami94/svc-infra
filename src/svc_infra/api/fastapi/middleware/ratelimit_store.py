from __future__ import annotations

import time
from typing import Optional, Protocol, Tuple


class RateLimitStore(Protocol):
    def incr(self, key: str, window: int) -> Tuple[int, int, int]:
        """Increment and return (count, limit, resetEpoch).

        Implementations should manage per-window buckets. The 'limit' is stored configuration.
        """
        ...


class InMemoryRateLimitStore:
    def __init__(self, limit: int = 120):
        self.limit = limit
        self._buckets: dict[tuple[str, int], int] = {}

    def incr(self, key: str, window: int) -> Tuple[int, int, int]:
        now = int(time.time())
        win = now - (now % window)
        count = self._buckets.get((key, win), 0) + 1
        self._buckets[(key, win)] = count
        reset = win + window
        return count, self.limit, reset


class RedisRateLimitStore:
    """Fixed-window counter store using Redis.

    Keys are of the form: {prefix}:{key}:{windowStart}
    Values are incremented and expire automatically at window end.

    This implementation uses atomic INCR and EXPIRE semantics. To avoid race conditions
    on first-set expiry, we set expiry when the counter is created.
    """

    def __init__(
        self,
        redis_client,
        *,
        limit: int = 120,
        prefix: str = "ratelimit",
        clock: Optional[callable] = None,
    ):
        self.redis = redis_client
        self.limit = limit
        self.prefix = prefix
        self._clock = clock or time.time

    def _window_key(self, key: str, window: int) -> tuple[str, int, str]:
        now = int(self._clock())
        win = now - (now % window)
        redis_key = f"{self.prefix}:{key}:{win}"
        return redis_key, win, now

    def incr(self, key: str, window: int) -> Tuple[int, int, int]:
        rkey, win, now = self._window_key(key, window)
        # Increment; if this is the first time we've seen this window key, set expiry to window end
        pipe = self.redis.pipeline()
        pipe.incr(rkey)
        pipe.ttl(rkey)
        count, ttl = pipe.execute()
        if ttl == -1:  # key exists without expire or just created; set expire to end of window
            expire_sec = (win + window) - now
            if expire_sec <= 0:
                expire_sec = window
            try:
                self.redis.expire(rkey, expire_sec)
            except Exception:
                pass
        reset = win + window
        return int(count), self.limit, reset


__all__ = ["RateLimitStore", "InMemoryRateLimitStore", "RedisRateLimitStore"]
