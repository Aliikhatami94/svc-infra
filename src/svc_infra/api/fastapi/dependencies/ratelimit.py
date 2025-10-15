from __future__ import annotations

import time
from typing import Callable

from fastapi import HTTPException
from starlette.requests import Request

from svc_infra.api.fastapi.middleware.ratelimit_store import InMemoryRateLimitStore, RateLimitStore
from svc_infra.obs.metrics import emit_rate_limited


class RateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window: int = 60,
        key_fn: Callable = lambda r: "global",
        store: RateLimitStore | None = None,
    ):
        self.limit = limit
        self.window = window
        self.key_fn = key_fn
        self.store = store or InMemoryRateLimitStore(limit=limit)

    async def __call__(self, request: Request):
        key = self.key_fn(request)
        count, limit, reset = self.store.incr(str(key), self.window)
        if count > limit:
            retry = max(0, reset - int(time.time()))
            try:
                emit_rate_limited(str(key), limit, retry)
            except Exception:
                pass
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(retry)}
            )


__all__ = ["RateLimiter"]


def rate_limiter(
    *,
    limit: int,
    window: int = 60,
    key_fn: Callable = lambda r: "global",
    store: RateLimitStore | None = None,
):
    store_ = store or InMemoryRateLimitStore(limit=limit)

    async def dep(request: Request):
        key = key_fn(request)
        count, lim, reset = store_.incr(str(key), window)
        if count > lim:
            retry = max(0, reset - int(time.time()))
            try:
                emit_rate_limited(str(key), lim, retry)
            except Exception:
                pass
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(retry)}
            )

    return dep
