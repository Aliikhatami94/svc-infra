import json
import logging

logger = logging.getLogger(__name__)

PROBLEM_MT = "application/problem+json"


class CatchAllExceptionMiddleware:
    """ASGI middleware that logs exceptions without breaking streaming (SSE)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
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
            logger.exception("Unhandled error on %s", scope.get("path"))

            if response_started:
                try:
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
                except Exception:
                    pass
            else:
                body = json.dumps(
                    {
                        "type": "about:blank",
                        "title": "Internal Server Error",
                        "status": 500,
                        "detail": str(exc),
                        "instance": scope.get("path", "/"),
                        "code": "INTERNAL_ERROR",
                    }
                ).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", PROBLEM_MT.encode("ascii"))],
                    }
                )
                await send({"type": "http.response.body", "body": body, "more_body": False})
