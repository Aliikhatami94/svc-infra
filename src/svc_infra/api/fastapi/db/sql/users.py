from __future__ import annotations

from typing import Any, AsyncIterator, Callable
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.manager import BaseUserManager, UUIDIDMixin

from svc_infra.auth.settings import get_auth_settings


def get_fastapi_users(
    user_model: Any,
    user_schema_read: Any,
    user_schema_create: Any,
    user_schema_update: Any,
    auth_prefix: str = "/auth",
) -> tuple[FastAPIUsers, AuthenticationBackend, APIRouter, APIRouter, Callable]:
    """Factory that wires FastAPI Users with JWT backend and returns routers.

    Returns: (fastapi_users, auth_backend, auth_router, users_router)
    """
    # Lazy import to avoid hard dependency at module import time
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    async def get_user_db(session) -> AsyncIterator[Any]:
        yield SQLAlchemyUserDatabase(session, user_model)

    class UserManager(UUIDIDMixin, BaseUserManager[Any, UUID]):
        reset_password_token_secret = "unused"
        verification_token_secret = "unused"

    async def get_user_manager(user_db=Depends(get_user_db)):
        yield UserManager(user_db)

    def get_jwt_strategy() -> JWTStrategy:
        settings = get_auth_settings()
        return JWTStrategy(
            secret=settings.jwt_secret.get_secret_value(),
            lifetime_seconds=settings.jwt_lifetime_seconds,
        )

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

    return fastapi_users, auth_backend, auth_router, users_router, get_jwt_strategy
