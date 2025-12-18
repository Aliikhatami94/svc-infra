from __future__ import annotations

import time

from svc_infra.api.fastapi.middleware.ratelimit_store import RedisRateLimitStore


class FakeRedis:
    def __init__(self):
        self.store: dict[str, tuple[int, float]] = {}

    def pipeline(self):
        return self

    # Pipeline ops
    def incr(self, key: str):
        v, _exp = self.store.get(key, (0, None))
        self._last_key = key
        self._incr_result = v + 1
        return self

    def ttl(self, key: str):
        _v, exp = self.store.get(key, (0, None))
        now = time.time()
        if exp is None:
            self._ttl_result = -1
        else:
            self._ttl_result = int(max(0, exp - now))
        return self

    def execute(self):
        # Apply incr
        if self._last_key not in self.store:
            self.store[self._last_key] = (1, None)
        else:
            v, exp = self.store[self._last_key]
            self.store[self._last_key] = (v + 1, exp)
        return (self.store[self._last_key][0], self._ttl_result)

    # Non-pipeline
    def expire(self, key: str, seconds: int):
        v, _ = self.store.get(key, (0, None))
        self.store[key] = (v, time.time() + seconds)


def test_redis_store_fixed_window_increments_and_sets_expiry(monkeypatch):
    fake = FakeRedis()
    store = RedisRateLimitStore(fake, limit=3, prefix="t", clock=lambda: 100)

    c1 = store.incr("k", 10)
    assert c1[0] == 1
    # ttl was -1 so expiry should be set
    assert fake.store["t:k:100"][1] is not None

    c2 = store.incr("k", 10)
    assert c2[0] == 2


def test_redis_store_window_rollover_sets_new_key(monkeypatch):
    fake = FakeRedis()
    t = 100
    store = RedisRateLimitStore(fake, limit=2, prefix="t", clock=lambda: t)

    c1 = store.incr("k", 10)  # window start 100
    assert c1[0] == 1
    t = 111  # move to next window
    store._clock = lambda: t
    c2 = store.incr("k", 10)
    # New window resets count
    assert c2[0] == 1
