from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from fastapi import Depends

from ..dual_router import DualAPIRouter
from .deps import make_optional_user_dep, make_require_roles_dep, make_require_user_dep


def _merge(base: Optional[Sequence[Any]], extra: Optional[Sequence[Any]]) -> list[Any]:
    out: list[Any] = []
    if base:
        out.extend(base)
    if extra:
        out.extend(extra)
    return out


def optional_user(
    *,
    session_dep,
    get_user_by_id: Callable,
    dependencies: Optional[Sequence[Any]] = None,
    **kwargs: Any,
) -> DualAPIRouter:
    dep = make_optional_user_dep(session_dep=session_dep, get_user_by_id=get_user_by_id)
    return DualAPIRouter(dependencies=_merge([Depends(dep)], dependencies), **kwargs)


def require_user(
    *,
    session_dep,
    get_user_by_id: Callable,
    dependencies: Optional[Sequence[Any]] = None,
    **kwargs: Any,
) -> DualAPIRouter:
    opt = make_optional_user_dep(session_dep=session_dep, get_user_by_id=get_user_by_id)
    req = make_require_user_dep(opt)
    return DualAPIRouter(dependencies=_merge([Depends(req)], dependencies), **kwargs)


def require_roles(
    *roles: str,
    session_dep,
    get_user_by_id: Callable,
    get_user_roles: Callable,
    dependencies: Optional[Sequence[Any]] = None,
    **kwargs: Any,
) -> DualAPIRouter:
    opt = make_optional_user_dep(session_dep=session_dep, get_user_by_id=get_user_by_id)
    req = make_require_user_dep(opt)
    rol = make_require_roles_dep(require_user_dep=req, get_user_roles=get_user_roles, roles=roles)
    return DualAPIRouter(dependencies=_merge([Depends(rol)], dependencies), **kwargs)
