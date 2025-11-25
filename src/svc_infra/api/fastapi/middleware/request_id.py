import contextvars
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdMiddleware:
    """Pure ASGI middleware that adds request IDs. Compatible with streaming responses."""

    def __init__(self, app: ASGIApp, header_name: str = "X-Request-Id"):
        self.app = app
        self.header_name = header_name.lower()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate request ID
        headers = Headers(scope=scope)
        rid = headers.get(self.header_name) or uuid4().hex
        token = request_id_ctx.set(rid)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Add request ID to response headers
                response_headers = MutableHeaders(scope=message)
                response_headers.append(self.header_name, rid)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_ctx.reset(token)
