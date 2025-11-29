from __future__ import annotations

from typing import Any

from ..openapi.apply import apply_default_responses, apply_default_security
from ..openapi.responses import DEFAULT_PUBLIC
from .router import DualAPIRouter


def public_router(**kwargs: Any) -> DualAPIRouter:
    """
    Public router: no auth dependencies.
    - Marks operations as public in OpenAPI (no lock icon) via security: []
    - Attaches standard reusable responses for public endpoints
    """
    r = DualAPIRouter(**kwargs)

    # Keep OpenAPI consistent with the other router factories
    apply_default_security(r, default_security=[])
    apply_default_responses(r, DEFAULT_PUBLIC)

    return r


def ws_public_router(**kwargs: Any) -> DualAPIRouter:
    """
    Public WebSocket router: no auth dependencies.

    Use this for WebSocket endpoints that don't require authentication.
    This is the WebSocket equivalent of `public_router()`.

    Example:
        router = ws_public_router(prefix="/api")

        @router.websocket("/ws/public")
        async def ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            # No auth required - anyone can connect
            async for msg in websocket.iter_json():
                await websocket.send_json({"echo": msg})
    """
    r = DualAPIRouter(**kwargs)

    # Keep OpenAPI consistent - no security requirement
    apply_default_security(r, default_security=[])

    return r
