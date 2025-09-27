from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from fastapi import Depends, HTTPException

from svc_infra.api.fastapi.auth.security import Identity, MaybeIdentity

from .router import DualAPIRouter


def _merge(base: Optional[Sequence[Any]], extra: Optional[Sequence[Any]]) -> list[Any]:
    out: list[Any] = []
    if base:
        out.extend(base)
    if extra:
        out.extend(extra)
    return out


def _apply_default_security(router: DualAPIRouter, default_security: list[dict] | None) -> None:
    """Wrap add_api_route to inject OpenAPI security if the operation didn’t set it."""
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


# OPTIONAL principal attached; **public looking** in docs
def optional_principal_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    async def _opt(p=MaybeIdentity):
        return p

    r = DualAPIRouter(dependencies=_merge([Depends(_opt)], dependencies), **kwargs)
    # Render as public in docs (no lock)
    _apply_default_security(r, default_security=[])
    return r


# PROTECTED (ANY): cookie/Bearer OR API key
def protected_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=_merge([Identity], dependencies), **kwargs)
    _apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
            {"ApiKeyHeader": []},
        ],
    )
    return r


# USER-ONLY: must be an authenticated user (API key alone is not enough)
def user_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
    async def _req_user(p=Identity):
        if not p.user:
            raise HTTPException(401, "user_required")
        return p

    r = DualAPIRouter(dependencies=_merge([Depends(_req_user)], dependencies), **kwargs)
    _apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
        ],
    )
    return r


# SERVICE-ONLY: must present a valid API key (no user needed)
def api_service_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    async def _req_service(p=Identity):
        if not p.api_key:
            raise HTTPException(401, "api_key_required")
        return p

    r = DualAPIRouter(dependencies=_merge([Depends(_req_service)], dependencies), **kwargs)
    _apply_default_security(r, default_security=[{"ApiKeyHeader": []}])
    return r


# ROLE-GATED: user with specific roles
def roles_router(
    *roles: str,
    role_resolver: Callable[[Any], list[str]] | None = None,
    dependencies: Optional[Sequence[Any]] = None,
    **kwargs: Any,
) -> DualAPIRouter:
    async def _req_roles(p=Identity):
        if not p.user:
            raise HTTPException(401, "user_required")
        have = set((role_resolver(p.user) if role_resolver else getattr(p.user, "roles", []) or []))
        if not set(roles).issubset(have):
            raise HTTPException(403, "forbidden")
        return p

    r = DualAPIRouter(dependencies=_merge([Depends(_req_roles)], dependencies), **kwargs)
    _apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
        ],
    )
    return r


def require_scopes(*needed: str):
    async def _dep(p=Identity):
        have = set(p.scopes or [])
        if not set(needed).issubset(have):
            raise HTTPException(403, "insufficient_scope")
        return p

    return _dep


def scopes_router(*scopes: str, **kwargs):
    async def _req(p=Depends(require_scopes(*scopes))):
        return p

    r = DualAPIRouter(dependencies=[Depends(_req)], **kwargs)
    _apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
            {"ApiKeyHeader": []},
        ],
    )
    return r
