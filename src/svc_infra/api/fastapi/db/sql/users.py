from __future__ import annotations

from typing import Any, AsyncIterator, Callable, Tuple
from uuid import UUID

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.manager import BaseUserManager, UUIDIDMixin

from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.dual.dualize import dualize_public, dualize_user
from svc_infra.api.fastapi.dual.router import DualAPIRouter
from svc_infra.app.env import CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV
from svc_infra.security.jwt_rotation import RotatingJWTStrategy

from ...auth.security import auth_login_path
from ...auth.sender import get_sender
from .session import SqlSessionDep


def get_fastapi_users(
    user_model: Any,
    user_schema_read: Any,
    user_schema_create: Any,
    user_schema_update: Any,
    *,
    public_auth_prefix: str = "/auth",
) -> Tuple[
    FastAPIUsers,
    AuthenticationBackend,
    DualAPIRouter,
    DualAPIRouter,
    Callable,
    DualAPIRouter,
    DualAPIRouter,
    DualAPIRouter,
]:
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    async def get_user_db(session: SqlSessionDep) -> AsyncIterator[Any]:
        yield SQLAlchemyUserDatabase(session, user_model)

    class UserManager(UUIDIDMixin, BaseUserManager[Any, UUID]):
        reset_password_token_secret = "unused"
        verification_token_secret = "unused"

        async def on_after_register(self, user: Any, request=None):
            st = get_auth_settings()
            if CURRENT_ENVIRONMENT in (DEV_ENV, LOCAL_ENV) and bool(st.auto_verify_in_dev):
                await self.user_db.update(user, {"is_verified": True})
                return
            await self.request_verify(user, request)

        async def on_after_request_verify(self, user: Any, token: str, request=None):
            verify_url = f"{public_auth_prefix}/verify?token={token}"
            sender = get_sender()
            sender.send(
                to=getattr(user, "email"),
                subject="Verify your account",
                html_body=f"""
                    <p>Hi {getattr(user, 'full_name', '') or 'there'},</p>
                    <p>Click to verify your account:</p>
                    <p><a href="{verify_url}">{verify_url}</a></p>
                """,
            )

        async def on_after_forgot_password(self, user: Any, token: str, request=None):
            reset_url = f"{public_auth_prefix}/reset-password?token={token}"
            sender = get_sender()
            sender.send(
                to=getattr(user, "email"),
                subject="Reset your password",
                html_body=f"""
                    <p>We received a request to reset your password.</p>
                    <p><a href="{reset_url}">{reset_url}</a></p>
                    <p>If you didn’t request this, you can ignore this email.</p>
                """,
            )

        async def on_after_reset_password(self, user: Any, request=None):
            # Optional: audit/log, notify, etc. Keep it no-op by default.
            pass

    async def get_user_manager(user_db=Depends(get_user_db)):
        yield UserManager(user_db)

    def get_jwt_strategy() -> JWTStrategy:
        st = get_auth_settings()
        jwt_block = getattr(st, "jwt", None)
        if jwt_block and getattr(jwt_block, "secret", None):
            secret = jwt_block.secret.get_secret_value()
        else:
            secret = "svc-dev-secret-change-me"
        lifetime = getattr(jwt_block, "lifetime_seconds", None) if jwt_block else None
        if not isinstance(lifetime, int) or lifetime <= 0:
            lifetime = 3600
        old = []
        if jwt_block and getattr(jwt_block, "old_secrets", None):
            old = [s.get_secret_value() for s in jwt_block.old_secrets or []]
        audience = "fastapi-users:auth"
        if old:
            return RotatingJWTStrategy(
                secret=secret,
                lifetime_seconds=lifetime,
                old_secrets=old,
                token_audience=audience,
            )
        return JWTStrategy(secret=secret, lifetime_seconds=lifetime, token_audience=audience)

    bearer_transport = BearerTransport(tokenUrl=auth_login_path)
    auth_backend = AuthenticationBackend(
        name="jwt", transport=bearer_transport, get_strategy=get_jwt_strategy
    )
    fastapi_users = FastAPIUsers(get_user_manager, [auth_backend])

    # IMPORTANT: requires_verification=True forces unverified users to be rejected on login.
    auth_router = dualize_public(
        fastapi_users.get_auth_router(auth_backend, requires_verification=True)
    )
    users_router = dualize_user(
        fastapi_users.get_users_router(user_schema_read, user_schema_update)
    )
    register_router = dualize_public(
        fastapi_users.get_register_router(user_schema_read, user_schema_create)
    )
    verify_router = dualize_public(fastapi_users.get_verify_router(user_schema_read))
    reset_router = dualize_public(fastapi_users.get_reset_password_router())

    return (
        fastapi_users,
        auth_backend,
        auth_router,
        users_router,
        get_jwt_strategy,
        register_router,
        verify_router,
        reset_router,
    )
