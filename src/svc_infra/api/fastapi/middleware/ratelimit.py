import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 120, window: int = 60, key_fn=None):
        super().__init__(app)
        self.limit, self.window = limit, window
        self.key_fn = key_fn or (lambda r: r.headers.get("X-API-Key") or r.client.host)
        self.buckets = {}  # replace with Redis in prod

    async def dispatch(self, request, call_next):
        key = self.key_fn(request)
        now = int(time.time())
        win = now - (now % self.window)
        bucket = self.buckets.setdefault((key, win), 0)

        remaining = self.limit - bucket
        reset = win + self.window

        if remaining <= 0:
            retry = max(0, reset - now)
            return JSONResponse(
                status_code=429,
                content={
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": "Rate limit exceeded.",
                    "code": "RATE_LIMITED",
                },
                headers={
                    "X-RateLimit-Limit": str(self.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset),
                    "Retry-After": str(retry),
                },
            )

        self.buckets[(key, win)] = bucket + 1
        resp = await call_next(request)
        resp.headers.setdefault("X-RateLimit-Limit", str(self.limit))
        resp.headers.setdefault("X-RateLimit-Remaining", str(self.limit - (bucket + 1)))
        resp.headers.setdefault("X-RateLimit-Reset", str(reset))
        return resp
