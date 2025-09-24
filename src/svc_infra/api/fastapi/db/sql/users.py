from __future__ import annotations

from typing import Any, AsyncIterator, Callable
from uuid import UUID

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.manager import BaseUserManager, UUIDIDMixin

from svc_infra.api.fastapi import DualAPIRouter, dualize_router
from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.deps import Require

from .session import SqlSessionDep


def get_fastapi_users(
    user_model: Any,
    user_schema_read: Any,
    user_schema_create: Any,
    user_schema_update: Any,
    auth_prefix: str = "/auth",
) -> tuple[FastAPIUsers, AuthenticationBackend, DualAPIRouter, DualAPIRouter, Callable]:
    """Factory that wires FastAPI Users with JWT backend and returns routers.

    Returns: (fastapi_users, auth_backend, auth_router, users_router)
    """
    # Lazy import to avoid hard dependency at module import time
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    async def get_user_db(session: SqlSessionDep) -> AsyncIterator[Any]:
        yield SQLAlchemyUserDatabase(session, user_model)

    class UserManager(UUIDIDMixin, BaseUserManager[Any, UUID]):
        reset_password_token_secret = "unused"
        verification_token_secret = "unused"

    async def get_user_manager(user_db=Require(get_user_db)):
        yield UserManager(user_db)

    def get_jwt_strategy() -> JWTStrategy:
        """
        Support nested settings:
          settings.jwt.secret (SecretStr)
          settings.jwt.lifetime_seconds (int)

        Falls back to safe dev defaults if unset (only for local/test).
        """
        settings = get_auth_settings()

        # Nested fields: settings.jwt.secret, settings.jwt.lifetime_seconds
        jwt_block = getattr(settings, "jwt", None)
        if jwt_block and getattr(jwt_block, "secret", None):
            secret = jwt_block.secret.get_secret_value()
        else:
            # dev/test fallback to avoid crashes; DO NOT use in prod
            secret = "svc-dev-secret-change-me"

        lifetime = getattr(jwt_block, "lifetime_seconds", None) if jwt_block else None
        if not isinstance(lifetime, int) or lifetime <= 0:
            lifetime = 3600  # 1 hour default

        return JWTStrategy(secret=secret, lifetime_seconds=lifetime)

    bearer_transport = BearerTransport(tokenUrl=f"{auth_prefix}/jwt/login")
    auth_backend = AuthenticationBackend(
        name="jwt",
        transport=bearer_transport,
        get_strategy=get_jwt_strategy,
    )

    fastapi_users = FastAPIUsers(get_user_manager, [auth_backend])
    auth_router = fastapi_users.get_auth_router(auth_backend, requires_verification=False)
    users_router = fastapi_users.get_users_router(
        user_schema_read, user_schema_create, user_schema_update
    )

    dual_auth_router = dualize_router(auth_router)
    dual_users_router = dualize_router(users_router)

    return fastapi_users, auth_backend, dual_auth_router, dual_users_router, get_jwt_strategy
