import json
import logging

logger = logging.getLogger(__name__)


class CatchAllExceptionMiddleware:
    """ASGI middleware that logs exceptions without breaking streaming (SSE)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only handle HTTP; pass through websockets, lifespan, etc.
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        response_started = False

        async def send_wrapper(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # We can only replace the response if it hasn't started yet.
            logger.exception("Unhandled error on %s", scope.get("path"))

            if response_started:
                # Can't change headers/status mid-stream; best effort to end stream.
                try:
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
                except Exception:
                    pass
            else:
                body = json.dumps(
                    {
                        "error": type(exc).__name__,
                        "detail": str(exc),
                    }
                ).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": body, "more_body": False})
