from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyCookie, APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy import select

from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.auth.state import get_auth_state, get_user_scope_resolver
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.paths.prefix import USER_PREFIX
from svc_infra.api.fastapi.paths.user import LOGIN_PATH
from svc_infra.db.sql.apikey import get_apikey_model

# ---------- OpenAPI security schemes (appear in docs) ----------
auth_login_path = USER_PREFIX + LOGIN_PATH
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=auth_login_path, auto_error=False)
cookie_auth_optional = APIKeyCookie(name=get_auth_settings().auth_cookie_name, auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------- Principal ----------
class Principal:
    """Unified identity: user via JWT/cookie or service via API key."""

    def __init__(
        self, *, user=None, scopes: list[str] | None = None, via: str = "jwt", api_key=None
    ):
        self.user = user
        self.scopes = scopes or []
        self.via = via  # "jwt" | "cookie" | "api_key"
        self.api_key = api_key


# ---------- Resolvers ----------
async def resolve_api_key(
    request: Request,
    session: SqlSessionDep,
) -> Optional[Principal]:
    raw = (request.headers.get("x-api-key") or "").strip()
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
    return Principal(user=apikey.user, scopes=apikey.scopes, via="api_key", api_key=apikey)


async def resolve_bearer_or_cookie_principal(
    request: Request, session: SqlSessionDep
) -> Optional[Principal]:
    st = get_auth_settings()
    raw_auth = (request.headers.get("authorization") or "").strip()
    token = raw_auth.split(" ", 1)[1].strip() if raw_auth.lower().startswith("bearer ") else ""
    if not token:
        token = (request.cookies.get(st.auth_cookie_name) or "").strip()
    if not token:
        return None

    UserModel, get_strategy, _ = get_auth_state()
    strategy = get_strategy()

    from fastapi_users.manager import BaseUserManager, UUIDIDMixin
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    user_db = SQLAlchemyUserDatabase(session, UserModel)

    class _ShimManager(UUIDIDMixin, BaseUserManager[Any, Any]):
        reset_password_token_secret = "unused"
        verification_token_secret = "unused"

        def __init__(self, db):
            super().__init__(db)

    user_manager = _ShimManager(user_db)

    try:
        user = await strategy.read_token(token, user_manager)
    except Exception:
        return None
    if not user:
        return None

    db_user = await session.get(UserModel, user.id)
    if not db_user:
        return None
    if not getattr(db_user, "is_active", True):
        raise HTTPException(401, "account_disabled")

    via = "jwt" if raw_auth else "cookie"
    user_scopes = get_user_scope_resolver()(db_user)
    # dedupe while keeping order
    scopes = list(dict.fromkeys(user_scopes))
    return Principal(user=db_user, scopes=scopes, via=via)


async def _current_principal(
    request: Request,
    session: SqlSessionDep,
    jwt_or_cookie: Optional[Principal] = Depends(resolve_bearer_or_cookie_principal),
    ak: Optional[Principal] = Depends(resolve_api_key),
) -> Principal:
    if jwt_or_cookie:
        return jwt_or_cookie
    if ak:
        return ak
    raise HTTPException(401, "Missing credentials")


async def _optional_principal(
    request: Request,
    session: SqlSessionDep,
    jwt_or_cookie: Optional[Principal] = Depends(resolve_bearer_or_cookie_principal),
    ak: Optional[Principal] = Depends(resolve_api_key),
) -> Optional[Principal]:
    return jwt_or_cookie or ak or None


# ---------- DX: types for endpoint params ----------
Identity = Annotated[Principal, Depends(_current_principal)]
OptionalIdentity = Annotated[Principal | None, Depends(_optional_principal)]

# ---------- DX: constants for router-level dependencies ----------
RequireIdentity = Depends(_current_principal)  # use inside router dependencies=[...]
AllowIdentity = Depends(_optional_principal)  # same, but optional


# ---------- DX: small guard factories ----------
def RequireRoles(*roles: str, resolver: Callable[[Any], list[str]] | None = None):
    async def _guard(p: Identity):
        have = set((resolver(p.user) if resolver else getattr(p.user, "roles", []) or []))
        if not set(roles).issubset(have):
            raise HTTPException(403, "forbidden")
        return p

    return Depends(_guard)


def RequireScopes(*needed: str):
    async def _guard(p: Identity):  # Identity = resolves to Principal
        if not set(needed).issubset(set(p.scopes or [])):
            raise HTTPException(403, "insufficient_scope")
        return p

    return Depends(_guard)


def RequireAnyScope(*candidates: str):
    async def _guard(p: Identity):
        if not set(p.scopes or []) & set(candidates):
            raise HTTPException(403, "insufficient_scope")
        return p

    return Depends(_guard)


def RequireUser():
    async def _guard(p: Identity):
        if not p.user:
            raise HTTPException(401, "user_required")
        return p

    return Depends(_guard)


def RequireService():
    async def _guard(p: Identity):
        if not p.api_key:
            raise HTTPException(401, "api_key_required")
        return p

    return Depends(_guard)
