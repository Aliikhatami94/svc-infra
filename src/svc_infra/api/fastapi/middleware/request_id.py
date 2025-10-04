import contextvars
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-Id"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request, call_next):
        rid = request.headers.get(self.header_name) or uuid4().hex
        token = request_id_ctx.set(rid)
        try:
            resp = await call_next(request)
            resp.headers[self.header_name] = rid
            return resp
        finally:
            request_id_ctx.reset(token)
