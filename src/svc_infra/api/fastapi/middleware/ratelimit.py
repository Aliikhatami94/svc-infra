import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from svc_infra.obs.metrics import emit_rate_limited

from .ratelimit_store import InMemoryRateLimitStore, RateLimitStore


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        limit: int = 120,
        window: int = 60,
        key_fn=None,
        store: RateLimitStore | None = None,
    ):
        super().__init__(app)
        self.limit, self.window = limit, window
        self.key_fn = key_fn or (lambda r: r.headers.get("X-API-Key") or r.client.host)
        self.store = store or InMemoryRateLimitStore(limit=limit)

    async def dispatch(self, request, call_next):
        key = self.key_fn(request)
        now = int(time.time())
        # Increment counter in store
        count, limit, reset = self.store.incr(str(key), self.window)
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
