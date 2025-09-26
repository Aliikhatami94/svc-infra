from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyCookie, APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy import select

from svc_infra.api.fastapi.auth.settings import get_auth_settings
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
    request: Request,
    session: SqlSessionDep,
) -> Optional[Principal]:
    """
    Try to authenticate a user via:
      1) Authorization: Bearer <jwt>
      2) auth cookie (settings.auth_cookie_name)
    Returns None if neither is present/valid (so caller can try API key).
    """
    st = get_auth_settings()

    raw_auth = (request.headers.get("authorization") or "").strip()
    raw_bearer = ""
    if raw_auth.lower().startswith("bearer "):
        raw_bearer = raw_auth.split(" ", 1)[1].strip()

    raw_cookie = (request.cookies.get(st.auth_cookie_name) or "").strip()

    token = raw_bearer or raw_cookie
    if not token:
        return None

    # so we avoid importing app-specific models here.
    # Discover User model via ApiKey relationship (only if API keys enabled)
    ApiKey = get_apikey_model()  # <-- LAZY here
    UserModel = ApiKey.user.property.mapper.class_

    # Defer import to avoid circulars and to keep this infra module reusable.
    from svc_infra.api.fastapi.db.sql.users import get_fastapi_users

    fapi, auth_backend, *_ = get_fastapi_users(
        UserModel, None, None, None, public_auth_prefix="/auth"
    )

    # fastapi-users needs a real user_manager instance to read tokens
    user_manager_gen = fapi.get_user_manager  # async generator
    strategy = auth_backend.get_strategy()

    user = None
    async for user_manager in user_manager_gen():  # type: ignore
        try:
            user = await strategy.read_token(token, user_manager)
        finally:
            break

    if not user:
        return None  # let API key fallback try

    # Rehydrate into *your* session so it's the real ORM instance
    db_user = await session.get(UserModel, user.id)
    if not db_user:
        return None

    # Enforce active status (keeps parity with your other guards)
    if not getattr(db_user, "is_active", True):
        raise HTTPException(401, "account_disabled")

    via = "jwt" if raw_bearer else "cookie"
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
