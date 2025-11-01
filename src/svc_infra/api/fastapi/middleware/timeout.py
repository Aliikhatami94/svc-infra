from __future__ import annotations

import asyncio
import os

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from svc_infra.api.fastapi.middleware.errors.handlers import problem_response
from svc_infra.app.env import pick


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


REQUEST_BODY_TIMEOUT_SECONDS: int = pick(
    prod=_env_int("REQUEST_BODY_TIMEOUT_SECONDS", 15),
    nonprod=_env_int("REQUEST_BODY_TIMEOUT_SECONDS", 30),
)
REQUEST_TIMEOUT_SECONDS: int = pick(
    prod=_env_int("REQUEST_TIMEOUT_SECONDS", 30),
    nonprod=_env_int("REQUEST_TIMEOUT_SECONDS", 15),
)


class HandlerTimeoutMiddleware:
    """
    Caps total handler execution time. If exceeded, returns 504 Problem+JSON.
    """

    def __init__(self, app: ASGIApp, timeout_seconds: int | None = None) -> None:
        self.app = app
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else REQUEST_TIMEOUT_SECONDS
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def _call_next() -> None:
            await self.app(scope, receive, send)

        try:
            await asyncio.wait_for(_call_next(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            # Build a minimal Request to extract headers and URL for trace info
            request = Request(scope, receive=receive)
            trace_id = None
            for h in ("x-request-id", "x-correlation-id", "x-trace-id"):
                v = request.headers.get(h)
                if v:
                    trace_id = v
                    break
            resp = problem_response(
                status=504,
                title="Gateway Timeout",
                detail="The request took too long to complete.",
                code="GATEWAY_TIMEOUT",
                instance=str(request.url),
                trace_id=trace_id,
            )
            await resp(scope, receive, send)


class BodyReadTimeoutMiddleware:
    """
    Enforces a timeout while reading the request body to mitigate slowloris.
    If body read does not make progress within the timeout, returns 408 Problem+JSON.
    """

    def __init__(self, app: ASGIApp, timeout_seconds: int | None = None) -> None:
        self.app = app
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else REQUEST_BODY_TIMEOUT_SECONDS
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # Strategy: greedily drain the incoming request body here while enforcing
        # per-receive timeout, then replay it to the downstream app from a buffer.
        # This ensures we can detect slowloris-style uploads even if the app only
        # reads the body later (after the server has finished buffering).
        buffered = bytearray()

        try:
            while True:
                message = await asyncio.wait_for(receive(), timeout=self.timeout_seconds)

                mtype = message.get("type")
                if mtype == "http.request":
                    chunk = message.get("body", b"") or b""
                    if chunk:
                        buffered.extend(chunk)
                    # Stop when server indicates no more body
                    if not message.get("more_body", False):
                        break
                    # else: continue reading remaining chunks with timeout
                    continue

                if mtype == "http.disconnect":  # client disconnected mid-upload
                    # Treat as end of body for the purposes of replay; downstream
                    # will see an empty body. No timeout response needed here.
                    break
                # Ignore other message types and continue
        except asyncio.TimeoutError:
            # Timed out while waiting for the next body chunk → return 408
            request = Request(scope, receive=receive)
            trace_id = None
            for h in ("x-request-id", "x-correlation-id", "x-trace-id"):
                v = request.headers.get(h)
                if v:
                    trace_id = v
                    break
            resp = problem_response(
                status=408,
                title="Request Timeout",
                detail="Timed out while reading request body.",
                code="REQUEST_TIMEOUT",
                instance=str(request.url),
                trace_id=trace_id,
            )
            await resp(scope, receive, send)
            return

        # Replay the drained body to the app as a single http.request message.
        sent = False

        async def _replay_receive() -> dict:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(buffered), "more_body": False}
            # Subsequent calls return an empty terminal body event
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, _replay_receive, send)
