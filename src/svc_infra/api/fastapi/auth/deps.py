from __future__ import annotations

from typing import Any, Callable, Optional, Sequence
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request

from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

AUDIENCE: Sequence[str] = ("fastapi-users:auth",)


def _cookie_name() -> str:
    st = get_auth_settings()
    return getattr(st, "auth_cookie_name", "svc_auth")


def _jwt_secret() -> str:
    st = get_auth_settings()
    jwt_cfg = getattr(st, "jwt", None)
    # Use same fallback you use elsewhere in local/dev
    return (
        jwt_cfg.secret.get_secret_value()
        if jwt_cfg and getattr(jwt_cfg, "secret", None)
        else "dev-change-me"
    )


async def _decode_cookie(request: Request) -> Optional[dict]:
    raw = request.cookies.get(_cookie_name())
    if not raw:
        return None
    try:
        return jwt.decode(raw, _jwt_secret(), algorithms=["HS256"], audience=list(AUDIENCE))
    except Exception:
        return None


def optional_user_dep_factory(user_model) -> Callable[..., Any]:
    """
    Returns a FastAPI dependency that tries to resolve a user from the cookie.
    - If no/invalid cookie: returns None
    - If valid: loads user by `sub` and returns it (can still be None if not found)
    Also writes `request.state.user` for convenience.
    """

    async def optional_user_dep(request: Request, session: SqlSessionDep):
        payload = await _decode_cookie(request)
        if not payload:
            request.state.user = None
            return None
        user_id = payload.get("sub")
        # sub is commonly a UUID; tolerate string input
        try:
            uid = UUID(str(user_id))
        except Exception:
            request.state.user = None
            return None
        user = await session.get(user_model, uid)
        request.state.user = user
        return user

    return optional_user_dep


def require_user_dep_factory(user_model):
    """Returns a dependency that 401s if no user is present."""
    optional_user = optional_user_dep_factory(user_model)

    async def require_user(user=Depends(optional_user)):
        if not user:
            raise HTTPException(status_code=401, detail="unauthenticated")
        return user

    return require_user


def require_roles_dep_factory(*roles: str, user_model):
    """
    Returns a dependency that enforces roles on top of `require_user`.
    """
    require_user = require_user_dep_factory(user_model)

    async def _inner(user=Depends(require_user)):
        user_roles = set(getattr(user, "roles", []) or [])
        needed = set(roles)
        if not needed.issubset(user_roles):
            raise HTTPException(status_code=403, detail="forbidden")
        return user

    return _inner
