from __future__ import annotations

import time
from typing import Protocol, Tuple


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


__all__ = ["RateLimitStore", "InMemoryRateLimitStore"]
