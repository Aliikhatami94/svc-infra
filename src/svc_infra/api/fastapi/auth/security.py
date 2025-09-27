from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyCookie, APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy import select

from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.auth.state import get_auth_state
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.db.sql.apikey import get_apikey_model

# Note: auto_error=False so these don't 403 if missing; we only want them to appear in OpenAPI.
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
cookie_auth_optional = APIKeyCookie(name=get_auth_settings().auth_cookie_name, auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class Principal:
    """A unified principal that can be a user (JWT/cookie/api-key) or a service principal."""

    def __init__(self, *, user=None, scopes: list[str] | None = None, via: str = "jwt"):
        self.user = user
        self.scopes = scopes or []
        self.via = via  # "jwt" | "cookie" | "api_key"


async def resolve_api_key(
    request: Request, session: SqlSessionDep, raw: Optional[str] = Security(api_key_header)
) -> Optional[Principal]:
    if not raw:
        return None

    ApiKey = get_apikey_model()

    prefix = ""
    parts = raw.split("_", 2)
    if len(parts) >= 3 and parts[0] == "ak":
        prefix = parts[1][:12]

    apikey = None
    if prefix:
        apikey = (
            (await session.execute(select(ApiKey).where(ApiKey.key_prefix == prefix)))
            .scalars()
            .first()
        )

    if not apikey:
        raise HTTPException(401, "invalid_api_key")

    from hmac import compare_digest

    if not compare_digest(ApiKey.hash(raw), apikey.key_hash):
        raise HTTPException(401, "invalid_api_key")

    if not apikey.active:
        raise HTTPException(401, "api_key_revoked")
    if apikey.expires_at and datetime.now(timezone.utc) > apikey.expires_at:
        raise HTTPException(401, "api_key_expired")

    apikey.mark_used()
    await session.flush()

    return Principal(user=apikey.user, scopes=apikey.scopes, via="api_key")


async def resolve_bearer_or_cookie_principal(
    request: Request, session: SqlSessionDep
) -> Optional[Principal]:
    st = get_auth_settings()

    raw_auth = (request.headers.get("authorization") or "").strip()
    token = ""
    if raw_auth.lower().startswith("bearer "):
        token = raw_auth.split(" ", 1)[1].strip()
    if not token:
        # try cookie
        token = (request.cookies.get(st.auth_cookie_name) or "").strip()
    if not token:
        return None

    # Use the exact UserModel and JWTStrategy from boot:
    UserModel, get_strategy, _ = get_auth_state()
    strategy = get_strategy()

    # We still need a user_manager to satisfy fastapi-users’ read_token signature,
    # but we don’t want to rebuild everything. Use a tiny, local manager shim.
    from fastapi_users.manager import BaseUserManager, UUIDIDMixin
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    user_db = SQLAlchemyUserDatabase(session, UserModel)

    class _ShimManager(UUIDIDMixin, BaseUserManager[Any, Any]):
        reset_password_token_secret = "unused"
        verification_token_secret = "unused"

        # fastapi-users only needs .user_db for read_token()
        def __init__(self, db):
            super().__init__(db)

    user_manager = _ShimManager(user_db)

    try:
        user = await strategy.read_token(token, user_manager)
    except Exception:
        return None
    if not user:
        return None

    # Rehydrate into your ORM session
    db_user = await session.get(UserModel, user.id)
    if not db_user:
        return None
    if not getattr(db_user, "is_active", True):
        raise HTTPException(401, "account_disabled")

    via = "jwt" if raw_auth else "cookie"
    return Principal(user=db_user, scopes=[], via=via)


async def current_principal(
    request: Request,
    session: SqlSessionDep,
    jwt_or_cookie: Optional[Principal] = Depends(resolve_bearer_or_cookie_principal),
    ak: Optional[Principal] = Depends(resolve_api_key),
) -> Principal:
    """
    Unified principal:
      - Bearer JWT (preferred)
      - auth cookie
      - X-API-Key
    Raises 401 if none are present/valid.
    """
    if jwt_or_cookie:
        return jwt_or_cookie
    if ak:
        return ak
    raise HTTPException(401, "Missing credentials")
