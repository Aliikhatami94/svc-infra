from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from fastapi import Depends, HTTPException

from ..dual_router import DualAPIRouter
from .security import current_principal


def _merge(base: Optional[Sequence[Any]], extra: Optional[Sequence[Any]]) -> list[Any]:
    out: list[Any] = []
    if base:
        out.extend(base)
    if extra:
        out.extend(extra)
    return out


# OPTIONAL: attach principal if present; never 401
def optional_principal_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    async def _opt(p=Depends(current_principal.optional)):  # uses .optional() helper
        return p

    return DualAPIRouter(dependencies=_merge([Depends(_opt)], dependencies), **kwargs)


# PROTECTED (ANY): cookie/Bearer OR API key
def protected_router(
    *, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    return DualAPIRouter(dependencies=_merge([Depends(current_principal)], dependencies), **kwargs)


# USER-ONLY: must be an authenticated user (API key alone is not enough)
def user_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
    async def _req_user(p=Depends(current_principal)):
        if not p.user:
            raise HTTPException(401, "user_required")
        return p

    return DualAPIRouter(dependencies=_merge([Depends(_req_user)], dependencies), **kwargs)


# SERVICE-ONLY: must present a valid API key (no user needed)
def service_router(*, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any) -> DualAPIRouter:
    async def _req_service(p=Depends(current_principal)):
        if not p.api_key:
            raise HTTPException(401, "api_key_required")
        return p

    return DualAPIRouter(dependencies=_merge([Depends(_req_service)], dependencies), **kwargs)


# ROLE-GATED: user with specific roles
def roles_router(
    *roles: str,
    role_resolver: Callable[[Any], list[str]] | None = None,
    dependencies: Optional[Sequence[Any]] = None,
    **kwargs: Any,
) -> DualAPIRouter:
    async def _req_roles(p=Depends(current_principal)):
        if not p.user:
            raise HTTPException(401, "user_required")
        have = set((role_resolver(p.user) if role_resolver else getattr(p.user, "roles", []) or []))
        if not set(roles).issubset(have):
            raise HTTPException(403, "forbidden")
        return p

    return DualAPIRouter(dependencies=_merge([Depends(_req_roles)], dependencies), **kwargs)
