from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int = 1_000_000):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request, call_next):
        length = request.headers.get("content-length")
        try:
            size = int(length) if length is not None else None
        except Exception:
            size = None
        if size is not None and size > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "title": "Payload Too Large",
                    "status": 413,
                    "detail": "Request body exceeds allowed size.",
                    "code": "PAYLOAD_TOO_LARGE",
                },
            )
        return await call_next(request)
