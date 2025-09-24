from __future__ import annotations

from typing import Any, List, Optional, Sequence

from fastapi import Depends

from svc_infra.api.fastapi.dual_router import DualAPIRouter

from .deps import optional_user_dep_factory, require_roles_dep_factory, require_user_dep_factory


def _merge_dependencies(
    base: Optional[Sequence[Any]],
    extra: Optional[Sequence[Any]],
) -> List[Any]:
    out: List[Any] = []
    if base:
        out.extend(base)
    if extra:
        out.extend(extra)
    return out


def public_router(**kwargs: Any) -> DualAPIRouter:
    """Unrestricted router."""
    return DualAPIRouter(**kwargs)


def optional_user(
    *, user_model, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    dep = optional_user_dep_factory(user_model)
    deps = _merge_dependencies([Depends(dep)], dependencies)
    return DualAPIRouter(dependencies=deps, **kwargs)


def require_user(
    *, user_model, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    dep = require_user_dep_factory(user_model)
    deps = _merge_dependencies([Depends(dep)], dependencies)
    return DualAPIRouter(dependencies=deps, **kwargs)


def require_roles(
    *roles: str, user_model, dependencies: Optional[Sequence[Any]] = None, **kwargs: Any
) -> DualAPIRouter:
    dep = require_roles_dep_factory(*roles, user_model=user_model)
    deps = _merge_dependencies([Depends(dep)], dependencies)
    return DualAPIRouter(dependencies=deps, **kwargs)
