import json
import time

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from svc_infra.obs.metrics import emit_rate_limited

from .ratelimit_store import InMemoryRateLimitStore, RateLimitStore

try:
    # Optional import: tenancy may not be enabled in all apps
    from svc_infra.api.fastapi.tenancy.context import (
        resolve_tenant_id as _resolve_tenant_id,
    )
except Exception:  # pragma: no cover - fallback for minimal builds
    _resolve_tenant_id = None  # type: ignore[assignment]


class SimpleRateLimitMiddleware:
    """
    Pure ASGI rate limiting middleware.

    Applies per-key rate limits with configurable windows. Use skip_paths for
    endpoints that should bypass rate limiting (e.g., health checks, webhooks).

    Matching uses prefix matching: "/v1/chat" matches "/v1/chat", "/v1/chat/stream",
    but not "/api/v1/chat" or "/v1/chatter".
    """

    def __init__(
        self,
        app: ASGIApp,
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
        skip_paths: list[str] | None = None,
    ):
        self.app = app
        self.limit, self.window = limit, window
        self.key_fn = key_fn
        self._limit_resolver = limit_resolver
        self.scope_by_tenant = scope_by_tenant
        self._allow_untrusted_tenant_header = allow_untrusted_tenant_header
        self.store = store or InMemoryRateLimitStore(limit=limit)
        self.skip_paths = skip_paths or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip specified paths using prefix matching
        if any(path.startswith(skip) for skip in self.skip_paths):
            await self.app(scope, receive, send)
            return

        # Create a Request object for key extraction and tenant resolution
        request = Request(scope, receive)

        # Default key function
        key_fn = self.key_fn or (
            lambda r: r.headers.get("X-API-Key") or (r.client.host if r.client else "unknown")
        )

        # Resolve tenant when possible
        tenant_id = None
        if self.scope_by_tenant or self._limit_resolver:
            try:
                if _resolve_tenant_id is not None:
                    tenant_id = await _resolve_tenant_id(request)
            except Exception:
                tenant_id = None
            # Fallback header behavior - ONLY if explicitly allowed
            # Never trust untrusted headers by default to prevent rate limit evasion
            if not tenant_id and self._allow_untrusted_tenant_header:
                tenant_id = request.headers.get("X-Tenant-Id") or request.headers.get("X-Tenant-ID")

        key = key_fn(request)
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
        count, _store_limit, reset = self.store.incr(str(key), self.window)
        limit = eff_limit
        remaining = max(0, limit - count)

        if count > limit:
            # Rate limited - return 429
            retry = max(0, reset - now)
            try:
                emit_rate_limited(str(key), limit, retry)
            except Exception:
                pass

            body = json.dumps(
                {
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": "Rate limit exceeded.",
                    "code": "RATE_LIMITED",
                }
            ).encode("utf-8")

            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"x-ratelimit-limit", str(limit).encode()),
                        (b"x-ratelimit-remaining", b"0"),
                        (b"x-ratelimit-reset", str(reset).encode()),
                        (b"retry-after", str(retry).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        # Not rate limited - add headers to response
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Add rate limit headers if not already present
                header_names = {h[0].lower() for h in headers}
                if b"x-ratelimit-limit" not in header_names:
                    headers.append((b"x-ratelimit-limit", str(limit).encode()))
                if b"x-ratelimit-remaining" not in header_names:
                    headers.append((b"x-ratelimit-remaining", str(remaining).encode()))
                if b"x-ratelimit-reset" not in header_names:
                    headers.append((b"x-ratelimit-reset", str(reset).encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
