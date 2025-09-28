from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from ..auth.security import (
    AllowIdentity,
    RequireIdentity,
    RequireRoles,
    RequireScopes,
    RequireService,
    RequireUser,
)
from ..openapi.responses import DEFAULT_PROTECTED, DEFAULT_PUBLIC, DEFAULT_SERVICE, DEFAULT_USER
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


def _apply_default_responses(router: DualAPIRouter, defaults: dict[int, dict]) -> None:
    """Automatically add standard error responses if the route didn't override them."""
    original_add = router.add_api_route

    def _wrapped_add_api_route(path: str, endpoint: Callable, **kwargs: Any):
        resp = kwargs.get("responses") or {}
        # only add codes that aren't already present
        for code, spec in defaults.items():
            resp.setdefault(code, spec)
        kwargs["responses"] = resp
        return original_add(path, endpoint, **kwargs)

    router.add_api_route = _wrapped_add_api_route  # type: ignore[attr-defined]


# PUBLIC (but attach OptionalIdentity for convenience)
def optional_identity_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([AllowIdentity], dependencies), **kwargs)
    _apply_default_security(r, default_security=[])  # public looking in docs
    _apply_default_responses(r, DEFAULT_PUBLIC)
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
    _apply_default_responses(r, DEFAULT_PROTECTED)
    return r


# USER-ONLY (no API-key-only access)
def user_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireUser()], dependencies), **kwargs)
    _apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    _apply_default_responses(r, DEFAULT_USER)
    return r


# SERVICE-ONLY (API key required)
def service_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([RequireService()], dependencies), **kwargs)
    _apply_default_security(r, default_security=[{"ApiKeyHeader": []}])
    _apply_default_responses(r, DEFAULT_SERVICE)
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
    _apply_default_responses(r, DEFAULT_PROTECTED)
    return r


# ROLE-GATED (example using roles attribute or resolver passed by caller)
def roles_router(*roles: str, role_resolver=None, **kwargs):
    r = DualAPIRouter(
        dependencies=[RequireUser(), RequireRoles(*roles, resolver=role_resolver)], **kwargs
    )
    _apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    _apply_default_responses(r, DEFAULT_USER)
    return r
