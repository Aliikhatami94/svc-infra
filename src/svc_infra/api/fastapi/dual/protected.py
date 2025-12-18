from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..auth.security import (
    AllowIdentity,
    RequireIdentity,
    RequireRoles,
    RequireScopes,
    RequireService,
    RequireUser,
)
from ..auth.ws_security import AllowWSIdentity, RequireWSIdentity, RequireWSScopes
from ..openapi.apply import apply_default_responses, apply_default_security
from ..openapi.responses import (
    DEFAULT_PROTECTED,
    DEFAULT_PUBLIC,
    DEFAULT_SERVICE,
    DEFAULT_USER,
)
from .router import DualAPIRouter


def _merge(base: Sequence[Any] | None, extra: Sequence[Any] | None) -> list[Any]:
    out: list[Any] = []
    if base:
        out.extend(base)
    if extra:
        out.extend(extra)
    return out


# PUBLIC (but attach OptionalIdentity for convenience)
def optional_identity_router(
    *, dependencies: Sequence[Any] | None = None, **kwargs: Any
) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([AllowIdentity], dependencies), **kwargs)
    apply_default_security(r, default_security=[])  # public looking in docs
    apply_default_responses(r, DEFAULT_PUBLIC)
    return r


# PROTECTED: any auth (JWT/cookie OR API key)
def protected_router(*, dependencies: Sequence[Any] | None = None, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireIdentity], dependencies), **kwargs)
    apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
            {"APIKeyHeader": []},
        ],
    )
    apply_default_responses(r, DEFAULT_PROTECTED)
    return r


# USER-ONLY (no API-key-only access)
def user_router(*, dependencies: Sequence[Any] | None = None, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireUser()], dependencies), **kwargs)
    apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    apply_default_responses(r, DEFAULT_USER)
    return r


# SERVICE-ONLY (API key required)
def service_router(*, dependencies: Sequence[Any] | None = None, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireService()], dependencies), **kwargs)
    apply_default_security(r, default_security=[{"APIKeyHeader": []}])
    apply_default_responses(r, DEFAULT_SERVICE)
    return r


# SCOPE-GATED (works with user scopes and api-key scopes)
def scopes_router(*scopes: str, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=[RequireIdentity, RequireScopes(*scopes)], **kwargs)
    apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
            {"APIKeyHeader": []},
        ],
    )
    apply_default_responses(r, DEFAULT_PROTECTED)
    return r


# ROLE-GATED (example using roles attribute or resolver passed by caller)
def roles_router(*roles: str, role_resolver=None, **kwargs):
    r = DualAPIRouter(
        dependencies=[RequireUser(), RequireRoles(*roles, resolver=role_resolver)],
        **kwargs,
    )
    apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    apply_default_responses(r, DEFAULT_USER)
    return r


# ---------- WebSocket Routers (Lightweight JWT, no DB required) ----------


def ws_protected_router(
    *, dependencies: Sequence[Any] | None = None, **kwargs: Any
) -> DualAPIRouter:
    """
    Protected WebSocket router - requires valid JWT token.

    Uses lightweight JWT validation (no database access required).
    Token can be passed via:
    - Query param: ?token=<jwt>
    - Header: Authorization: Bearer <jwt>
    - Cookie: auth cookie
    - Subprotocol: access_token.<jwt>

    Example:
        router = ws_protected_router()

        @router.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket, principal: WSIdentity):
            user_id = str(principal.id)
            await websocket.accept()
            ...
    """
    r = DualAPIRouter(dependencies=_merge([RequireWSIdentity], dependencies), **kwargs)
    # WebSocket doesn't have OpenAPI security, but we set it for documentation
    apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    return r


def ws_optional_router(
    *, dependencies: Sequence[Any] | None = None, **kwargs: Any
) -> DualAPIRouter:
    """
    Optional auth WebSocket router - allows anonymous connections.

    If a valid JWT is provided, principal will be set.
    If no token or invalid token, principal will be None.

    Example:
        router = ws_optional_router()

        @router.websocket("/ws/public")
        async def ws_endpoint(websocket: WebSocket, principal: WSOptionalIdentity):
            user_id = str(principal.id) if principal else "anonymous"
            await websocket.accept()
            ...
    """
    r = DualAPIRouter(dependencies=_merge([AllowWSIdentity], dependencies), **kwargs)
    apply_default_security(r, default_security=[])
    return r


def ws_user_router(*, dependencies: Sequence[Any] | None = None, **kwargs: Any) -> DualAPIRouter:
    """
    User-only WebSocket router - requires valid user JWT (no API key).

    Uses lightweight JWT validation (no database access required).
    This is the WebSocket equivalent of `user_router()`.

    Example:
        router = ws_user_router()

        @router.websocket("/ws/user")
        async def ws_endpoint(websocket: WebSocket, principal: WSIdentity):
            # principal.id, principal.email, principal.scopes from JWT
            await websocket.accept()
            ...
    """
    r = DualAPIRouter(dependencies=_merge([RequireWSIdentity], dependencies), **kwargs)
    apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    return r


def ws_scopes_router(
    *scopes: str, dependencies: Sequence[Any] | None = None, **kwargs: Any
) -> DualAPIRouter:
    """
    Scope-gated WebSocket router - requires valid JWT with specific scopes.

    Uses lightweight JWT validation (no database access required).
    This is the WebSocket equivalent of `scopes_router()`.

    Example:
        router = ws_scopes_router("chat:read", "chat:write")

        @router.websocket("/ws/chat")
        async def ws_endpoint(websocket: WebSocket, principal: WSIdentity):
            # principal has verified scopes
            await websocket.accept()
            ...
    """
    r = DualAPIRouter(
        dependencies=_merge([RequireWSIdentity, RequireWSScopes(*scopes)], dependencies),
        **kwargs,
    )
    apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    return r
