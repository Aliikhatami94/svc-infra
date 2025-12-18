"""WebSocket authentication primitives.

This module provides lightweight JWT-based authentication for WebSocket endpoints.
Unlike HTTP auth which requires DB access, WS auth uses JWT claims only, making it
suitable for high-frequency real-time connections.

Usage:
    from svc_infra.api.fastapi.auth.ws_security import WSIdentity

    @router.websocket("/ws")
    async def ws_handler(websocket: WebSocket, user: WSIdentity):
        # user.id, user.email, user.scopes available from JWT claims
        await websocket.accept()
        ...

For router-level dependencies (protects all endpoints):
    from svc_infra.api.fastapi.auth.ws_security import RequireWSIdentity

    router = DualAPIRouter(dependencies=[RequireWSIdentity])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, cast

import jwt
from fastapi import Depends, WebSocket, WebSocketException, status

from svc_infra.api.fastapi.auth.settings import get_auth_settings


# ---------- WSPrincipal ----------
@dataclass
class WSPrincipal:
    """Lightweight principal for WebSocket connections.

    Unlike the HTTP `Principal` which loads the full user from DB,
    `WSPrincipal` contains only JWT claims. This makes it suitable
    for high-frequency real-time connections without DB overhead.

    Attributes:
        id: User ID from JWT 'sub' claim (typically UUID string)
        email: User email from JWT 'email' claim (if present)
        scopes: List of scopes/permissions from JWT 'scopes' claim
        claims: Full JWT payload for custom claim access
        via: Authentication method ('query', 'header', 'subprotocol')
    """

    id: str
    email: str | None = None
    scopes: list[str] = field(default_factory=list)
    claims: dict = field(default_factory=dict)
    via: str = "query"  # 'query' | 'header' | 'subprotocol'


# ---------- Token extraction ----------
def _extract_token(websocket: WebSocket) -> tuple[str | None, str]:
    """Extract JWT token from WebSocket connection.

    Tries extraction in order:
    1. Query parameter: ?token=xxx
    2. Authorization header: Bearer xxx
    3. Sec-WebSocket-Protocol header (for browser clients that can't set headers)

    Returns:
        Tuple of (token, source) where source is 'query', 'header', or 'subprotocol'
    """
    # 1. Query parameter (most common for WebSocket)
    token = websocket.query_params.get("token")
    if token:
        return token.strip(), "query"

    # 2. Authorization header
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return token, "header"

    # 3. Sec-WebSocket-Protocol (browser workaround)
    # Some clients send token as: Sec-WebSocket-Protocol: bearer, <token>
    protocol = websocket.headers.get("sec-websocket-protocol", "")
    if protocol:
        parts = [p.strip() for p in protocol.split(",")]
        # Look for token after 'bearer' protocol
        for i, part in enumerate(parts):
            if part.lower() == "bearer" and i + 1 < len(parts):
                return parts[i + 1], "subprotocol"

    return None, ""


def _decode_jwt(token: str) -> dict:
    """Decode and validate JWT token.

    Uses the same JWT settings as HTTP auth (AUTH_JWT__SECRET).
    Supports key rotation via old_secrets.

    Returns:
        JWT payload dict

    Raises:
        WebSocketException: If token is invalid or expired
    """
    settings = get_auth_settings()

    if not settings.jwt:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="JWT not configured",
        )

    secret = settings.jwt.secret.get_secret_value()
    old_secrets = [s.get_secret_value() for s in (settings.jwt.old_secrets or [])]
    all_secrets = [secret, *old_secrets]

    last_error: Exception | None = None

    for s in all_secrets:
        try:
            payload = jwt.decode(
                token,
                s,
                algorithms=["HS256"],
                options={"require": ["sub", "exp"]},
            )
            return cast("dict[Any, Any]", payload)
        except jwt.ExpiredSignatureError:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Token expired",
            )
        except jwt.InvalidTokenError as e:
            last_error = e
            continue

    # None of the secrets worked
    raise WebSocketException(
        code=status.WS_1008_POLICY_VIOLATION,
        reason=f"Invalid token: {last_error}",
    )


# ---------- Resolvers ----------
async def resolve_ws_bearer_principal(websocket: WebSocket) -> WSPrincipal | None:
    """Extract and validate JWT from WebSocket, returning WSPrincipal or None.

    This is the optional resolver - returns None if no token present.
    Use `_ws_current_principal` for required authentication.

    Token sources (in order):
        1. Query parameter: ?token=xxx
        2. Authorization header: Bearer xxx
        3. Sec-WebSocket-Protocol: bearer, xxx
    """
    token, source = _extract_token(websocket)
    if not token:
        return None

    payload = _decode_jwt(token)

    return WSPrincipal(
        id=str(payload.get("sub", "")),
        email=payload.get("email"),
        scopes=payload.get("scopes", []) or payload.get("scope", "").split(),
        claims=payload,
        via=source,
    )


async def _ws_current_principal(
    websocket: WebSocket,
    principal: WSPrincipal | None = Depends(resolve_ws_bearer_principal),
) -> WSPrincipal:
    """Require authenticated WebSocket connection.

    Use this as a dependency to require authentication.
    Closes connection with 1008 (Policy Violation) if no valid token.
    """
    if not principal:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing or invalid authentication",
        )
    return principal


async def _ws_optional_principal(
    websocket: WebSocket,
    principal: WSPrincipal | None = Depends(resolve_ws_bearer_principal),
) -> WSPrincipal | None:
    """Optional WebSocket authentication.

    Returns None if no token present, WSPrincipal if valid token.
    """
    return principal


# ---------- DX: types for endpoint params ----------
WSIdentity = Annotated[WSPrincipal, Depends(_ws_current_principal)]
"""Annotated type for required WebSocket authentication.

Usage:
    @router.websocket("/ws")
    async def handler(websocket: WebSocket, user: WSIdentity):
        # user.id, user.email, user.scopes available
        ...
"""

OptionalWSIdentity = Annotated[WSPrincipal | None, Depends(_ws_optional_principal)]
"""Annotated type for optional WebSocket authentication.

Usage:
    @router.websocket("/ws")
    async def handler(websocket: WebSocket, user: OptionalWSIdentity):
        if user:
            # authenticated
        else:
            # anonymous
        ...
"""


# ---------- DX: constants for router-level dependencies ----------
RequireWSIdentity = Depends(_ws_current_principal)
"""Router-level dependency for required WebSocket authentication.

Usage:
    router = DualAPIRouter(dependencies=[RequireWSIdentity])
"""

AllowWSIdentity = Depends(_ws_optional_principal)
"""Router-level dependency for optional WebSocket authentication.

Usage:
    router = DualAPIRouter(dependencies=[AllowWSIdentity])
"""


# ---------- DX: guard factories ----------
def RequireWSScopes(*needed: str):
    """Require specific scopes for WebSocket connection.

    Usage:
        router = DualAPIRouter(dependencies=[RequireWSScopes("chat:read", "chat:write")])
    """

    async def _guard(principal: WSIdentity) -> WSPrincipal:
        if not set(needed).issubset(set(principal.scopes or [])):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Insufficient scope",
            )
        return principal

    return Depends(_guard)


def RequireWSAnyScope(*candidates: str):
    """Require at least one of the specified scopes.

    Usage:
        router = DualAPIRouter(dependencies=[RequireWSAnyScope("admin", "moderator")])
    """

    async def _guard(principal: WSIdentity) -> WSPrincipal:
        if not set(principal.scopes or []) & set(candidates):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Insufficient scope",
            )
        return principal

    return Depends(_guard)
