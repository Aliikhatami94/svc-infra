from __future__ import annotations

from typing import Any, Optional, Sequence

from ..auth.security import (
    AllowIdentity,
    RequireIdentity,
    RequireRoles,
    RequireScopes,
    RequireService,
    RequireUser,
)
from ..openapi.apply import apply_default_responses, apply_default_security
from ..openapi.responses import DEFAULT_PROTECTED, DEFAULT_PUBLIC, DEFAULT_SERVICE, DEFAULT_USER
from .router import DualAPIRouter


def _merge(base: Optional[Sequence[Any]], extra: Optional[Sequence[Any]]) -> list[Any]:
    out: list[Any] = []
    if base:
        out.extend(base)
    if extra:
        out.extend(extra)
    return out


# PUBLIC (but attach OptionalIdentity for convenience)
def optional_identity_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([AllowIdentity], dependencies), **kwargs)
    apply_default_security(r, default_security=[])  # public looking in docs
    apply_default_responses(r, DEFAULT_PUBLIC)
    return r


# PROTECTED: any auth (JWT/cookie OR API key)
def protected_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
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
def user_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireUser()], dependencies), **kwargs)
    apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    apply_default_responses(r, DEFAULT_USER)
    return r


# SERVICE-ONLY (API key required)
def service_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
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
        dependencies=[RequireUser(), RequireRoles(*roles, resolver=role_resolver)], **kwargs
    )
    apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    apply_default_responses(r, DEFAULT_USER)
    return r
