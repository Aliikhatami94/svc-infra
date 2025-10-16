from __future__ import annotations

import time
from typing import Callable, Optional

from fastapi import HTTPException
from starlette.requests import Request

from svc_infra.api.fastapi.middleware.ratelimit_store import InMemoryRateLimitStore, RateLimitStore

try:
    from svc_infra.api.fastapi.tenancy.context import resolve_tenant_id as _resolve_tenant_id
except Exception:  # pragma: no cover - minimal builds
    _resolve_tenant_id = None  # type: ignore
from svc_infra.obs.metrics import emit_rate_limited


class RateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window: int = 60,
        key_fn: Callable = lambda r: "global",
        limit_resolver: Optional[Callable[[Request, Optional[str]], Optional[int]]] = None,
        scope_by_tenant: bool = False,
        store: RateLimitStore | None = None,
    ):
        self.limit = limit
        self.window = window
        self.key_fn = key_fn
        self._limit_resolver = limit_resolver
        self.scope_by_tenant = scope_by_tenant
        self.store = store or InMemoryRateLimitStore(limit=limit)

    async def __call__(self, request: Request):
        # Try resolving tenant when asked
        tenant_id = None
        if self.scope_by_tenant or self._limit_resolver:
            try:
                if _resolve_tenant_id is not None:
                    tenant_id = await _resolve_tenant_id(request)
            except Exception:
                tenant_id = None

        key = self.key_fn(request)
        if self.scope_by_tenant and tenant_id:
            key = f"{key}:tenant:{tenant_id}"

        eff_limit = self.limit
        if self._limit_resolver:
            try:
                v = self._limit_resolver(request, tenant_id)
                eff_limit = int(v) if v is not None else self.limit
            except Exception:
                eff_limit = self.limit

        count, store_limit, reset = self.store.incr(str(key), self.window)
        if count > eff_limit:
            retry = max(0, reset - int(time.time()))
            try:
                emit_rate_limited(str(key), eff_limit, retry)
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
    limit_resolver: Optional[Callable[[Request, Optional[str]], Optional[int]]] = None,
    scope_by_tenant: bool = False,
    store: RateLimitStore | None = None,
):
    store_ = store or InMemoryRateLimitStore(limit=limit)

    async def dep(request: Request):
        tenant_id = None
        if scope_by_tenant or limit_resolver:
            try:
                if _resolve_tenant_id is not None:
                    tenant_id = await _resolve_tenant_id(request)
            except Exception:
                tenant_id = None

        key = key_fn(request)
        if scope_by_tenant and tenant_id:
            key = f"{key}:tenant:{tenant_id}"

        eff_limit = limit
        if limit_resolver:
            try:
                v = limit_resolver(request, tenant_id)
                eff_limit = int(v) if v is not None else limit
            except Exception:
                eff_limit = limit

        count, _store_limit, reset = store_.incr(str(key), window)
        if count > eff_limit:
            retry = max(0, reset - int(time.time()))
            try:
                emit_rate_limited(str(key), eff_limit, retry)
            except Exception:
                pass
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(retry)}
            )

    return dep
