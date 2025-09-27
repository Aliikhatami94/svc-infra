from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from svc_infra.api.fastapi.auth.security import RequireIdentity  # for router-level dependencies
from svc_infra.api.fastapi.auth.security import RequireScopes  # guard factory
from svc_infra.api.fastapi.auth.security import RequireService  # guard factory
from svc_infra.api.fastapi.auth.security import RequireUser  # guard factory
from svc_infra.api.fastapi.auth.security import (  # for router-level dependencies
    AllowIdentity,
    RequireRoles,
)

from .router import DualAPIRouter


def _merge(base: Optional[Sequence[Any]], extra: Optional[Sequence[Any]]) -> list[Any]:
    out: list[Any] = []
    if base:
        out.extend(base)
    if extra:
        out.extend(extra)
    return out


def _apply_default_security(router: DualAPIRouter, default_security: list[dict] | None) -> None:
    if default_security is None:
        return
    original_add = router.add_api_route

    def _wrapped_add_api_route(path: str, endpoint: Callable, **kwargs: Any):
        ox = kwargs.get("openapi_extra") or {}
        if "security" not in ox:
            ox["security"] = default_security
            kwargs["openapi_extra"] = ox
        return original_add(path, endpoint, **kwargs)

    router.add_api_route = _wrapped_add_api_route  # type: ignore[attr-defined]


# PUBLIC (but attach OptionalIdentity for convenience)
def optional_identity_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([AllowIdentity], dependencies), **kwargs)
    _apply_default_security(r, default_security=[])  # public looking in docs
    return r


# PROTECTED: any auth (JWT/cookie OR API key)
def protected_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireIdentity], dependencies), **kwargs)
    _apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
            {"ApiKeyHeader": []},
        ],
    )
    return r


# USER-ONLY (no API-key-only access)
def user_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireUser()], dependencies), **kwargs)
    _apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    return r


# SERVICE-ONLY (API key required)
def service_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireService()], dependencies), **kwargs)
    _apply_default_security(r, default_security=[{"ApiKeyHeader": []}])
    return r


# SCOPE-GATED (works with user scopes and api-key scopes)
def scopes_router(*scopes: str, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=[RequireIdentity, RequireScopes(*scopes)], **kwargs)
    _apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
            {"ApiKeyHeader": []},
        ],
    )
    return r


# ROLE-GATED (example using roles attribute or resolver passed by caller)
def roles_router(*roles: str, role_resolver=None, **kwargs):
    r = DualAPIRouter(
        dependencies=[RequireUser(), RequireRoles(*roles, resolver=role_resolver)], **kwargs
    )
    _apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    return r
