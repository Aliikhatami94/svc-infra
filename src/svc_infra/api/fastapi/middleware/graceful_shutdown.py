from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from svc_infra.app.env import pick

logger = logging.getLogger(__name__)


def _get_grace_period_seconds() -> float:
    default = pick(prod=20.0, nonprod=5.0)
    raw = os.getenv("SHUTDOWN_GRACE_PERIOD_SECONDS")
    if raw is None or raw == "":
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


class InflightTrackerMiddleware:
    """Tracks number of in-flight requests to support graceful shutdown drains."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        state = scope.get("app").state  # type: ignore[attr-defined]
        state._inflight_requests = getattr(state, "_inflight_requests", 0) + 1
        try:
            await self.app(scope, receive, send)
        finally:
            state._inflight_requests = max(0, getattr(state, "_inflight_requests", 1) - 1)


async def _wait_for_drain(app: FastAPI, grace: float) -> None:
    interval = 0.1
    waited = 0.0
    while waited < grace:
        inflight = int(getattr(app.state, "_inflight_requests", 0))
        if inflight <= 0:
            return
        await asyncio.sleep(interval)
        waited += interval
    inflight = int(getattr(app.state, "_inflight_requests", 0))
    if inflight > 0:
        logger.warning(
            "Graceful shutdown timeout: %s in-flight request(s) after %.2fs", inflight, waited
        )


def install_graceful_shutdown(app: FastAPI, *, grace_seconds: Optional[float] = None) -> None:
    """Install inflight tracking and lifespan hooks to wait for requests to drain.

    - Adds InflightTrackerMiddleware
    - Registers a lifespan handler that initializes state and waits up to grace_seconds on shutdown
    """
    app.add_middleware(InflightTrackerMiddleware)

    g = float(grace_seconds) if grace_seconds is not None else _get_grace_period_seconds()

    # Preserve any existing lifespan and wrap it so our drain runs on shutdown.
    previous_lifespan = getattr(app.router, "lifespan_context", None)

    @asynccontextmanager
    async def _lifespan(a: FastAPI):  # noqa: ANN202
        # Startup: initialize inflight counter
        a.state._inflight_requests = 0
        if previous_lifespan is not None:
            async with previous_lifespan(a):
                yield
        else:
            yield
        # Shutdown: wait for in-flight requests to drain (up to grace period)
        await _wait_for_drain(a, g)

    app.router.lifespan_context = _lifespan
