import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from svc_infra.obs.metrics import emit_rate_limited

from .ratelimit_store import InMemoryRateLimitStore, RateLimitStore

try:
    # Optional import: tenancy may not be enabled in all apps
    from svc_infra.api.fastapi.tenancy.context import resolve_tenant_id as _resolve_tenant_id
except Exception:  # pragma: no cover - fallback for minimal builds
    _resolve_tenant_id = None  # type: ignore


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        limit: int = 120,
        window: int = 60,
        key_fn=None,
        *,
        # When provided, dynamically computes a limit for the current request (e.g. per-tenant quotas)
        # Signature: (request: Request, tenant_id: Optional[str]) -> int | None
        limit_resolver=None,
        # If True, automatically scopes the bucket key by tenant id when available
        scope_by_tenant: bool = False,
        # When True, allows unresolved tenant IDs to fall back to an "X-Tenant-Id" header value.
        # Disabled by default to avoid trusting arbitrary client-provided headers which could
        # otherwise be used to evade per-tenant limits when authentication fails.
        allow_untrusted_tenant_header: bool = False,
        store: RateLimitStore | None = None,
    ):
        super().__init__(app)
        self.limit, self.window = limit, window
        self.key_fn = key_fn or (lambda r: r.headers.get("X-API-Key") or r.client.host)
        self._limit_resolver = limit_resolver
        self.scope_by_tenant = scope_by_tenant
        self._allow_untrusted_tenant_header = allow_untrusted_tenant_header
        self.store = store or InMemoryRateLimitStore(limit=limit)

    async def dispatch(self, request, call_next):
        # Resolve tenant when possible
        tenant_id = None
        if self.scope_by_tenant or self._limit_resolver:
            try:
                if _resolve_tenant_id is not None:
                    tenant_id = await _resolve_tenant_id(request)
            except Exception:
                tenant_id = None
            # Fallback header behavior:
            # - If tenancy context is unavailable (minimal builds), accept header by default so
            #   unit/integration tests can exercise per-tenant scoping without full auth state.
            # - If tenancy is available, only trust the header when explicitly allowed.
            if not tenant_id:
                if _resolve_tenant_id is None:
                    tenant_id = request.headers.get("X-Tenant-Id") or request.headers.get(
                        "X-Tenant-ID"
                    )
                elif self._allow_untrusted_tenant_header:
                    tenant_id = request.headers.get("X-Tenant-Id") or request.headers.get(
                        "X-Tenant-ID"
                    )

        key = self.key_fn(request)
        if self.scope_by_tenant and tenant_id:
            key = f"{key}:tenant:{tenant_id}"

        # Allow dynamic limit overrides
        eff_limit = self.limit
        if self._limit_resolver:
            try:
                v = self._limit_resolver(request, tenant_id)
                eff_limit = int(v) if v is not None else self.limit
            except Exception:
                eff_limit = self.limit

        now = int(time.time())
        # Increment counter in store
        # Update store limit if it differs; stores capture configured limit internally
        # For in-memory store, we can temporarily adjust per-request by swapping a new store instance
        # but to keep API simple, we reuse store and clamp by eff_limit below.
        count, store_limit, reset = self.store.incr(str(key), self.window)
        # Enforce the effective limit selected for this request
        limit = eff_limit
        remaining = max(0, limit - count)

        if remaining < 0:  # defensive clamp
            remaining = 0

        if count > limit:
            retry = max(0, reset - now)
            try:
                emit_rate_limited(str(key), limit, retry)
            except Exception:
                pass
            return JSONResponse(
                status_code=429,
                content={
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": "Rate limit exceeded.",
                    "code": "RATE_LIMITED",
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset),
                    "Retry-After": str(retry),
                },
            )

        resp = await call_next(request)
        resp.headers.setdefault("X-RateLimit-Limit", str(limit))
        resp.headers.setdefault("X-RateLimit-Remaining", str(remaining))
        resp.headers.setdefault("X-RateLimit-Reset", str(reset))
        return resp
