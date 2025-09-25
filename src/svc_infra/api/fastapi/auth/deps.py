from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, Sequence

import jwt
from fastapi import Depends, HTTPException, Request

from ..auth.settings import get_auth_settings

AUDIENCE = ["fastapi-users:auth"]

GetSessionDep = Any  # FastAPI dep marker provided by adapters
GetUserById = Callable[[Any, Any], Awaitable[Optional[Any]]]
GetUserRoles = Callable[[Any], Sequence[str]]


def make_optional_user_dep(*, session_dep: GetSessionDep, get_user_by_id: GetUserById):
    async def optional_user(request: Request, session=Depends(session_dep)):
        st = get_auth_settings()
        cookie_name = getattr(st, "auth_cookie_name", "svc_auth")
        raw = request.cookies.get(cookie_name)
        if not raw:
            request.state.user = None
            return None
        try:
            payload = jwt.decode(
                raw, st.jwt.secret.get_secret_value(), algorithms=["HS256"], audience=AUDIENCE
            )
        except Exception:
            request.state.user = None
            return None
        user = await get_user_by_id(session, payload.get("sub"))
        request.state.user = user
        return user

    return optional_user


def make_require_user_dep(optional_user_dep):
    async def require_user(user=Depends(optional_user_dep)):
        if not user:
            raise HTTPException(401, "unauthenticated")
        return user

    return require_user


def make_require_roles_dep(*, require_user_dep, get_user_roles: GetUserRoles, roles: Sequence[str]):
    async def require_roles(user=Depends(require_user_dep)):
        if not set(roles).issubset(set(get_user_roles(user) or [])):
            raise HTTPException(403, "forbidden")
        return user

    return require_roles
