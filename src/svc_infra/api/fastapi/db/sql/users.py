from __future__ import annotations

from typing import Any, AsyncIterator, Callable, Tuple
from uuid import UUID

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.manager import BaseUserManager, UUIDIDMixin

from svc_infra.api.fastapi import DualAPIRouter, dualize_router
from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.deps import Require
from svc_infra.app.env import CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV

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
]:
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    async def get_user_db(session: SqlSessionDep) -> AsyncIterator[Any]:
        yield SQLAlchemyUserDatabase(session, user_model)

    class UserManager(UUIDIDMixin, BaseUserManager[Any, UUID]):
        reset_password_token_secret = "unused"
        verification_token_secret = "unused"

        async def on_after_register(self, user: Any, request=None):
            # Dev convenience: optionally auto-verify
            st = get_auth_settings()
            if CURRENT_ENVIRONMENT in (DEV_ENV, LOCAL_ENV) and bool(st.auto_verify_in_dev):
                try:
                    await self.verify(user, safe=True)
                    return
                except Exception:
                    # fall through to email flow
                    pass

            # Otherwise send verification email (prod MUST have SMTP)
            token = await self.generate_verification_token(user)
            verify_url = f"{public_auth_prefix}/verify?token={token}"
            sender = get_sender()  # raises in prod if not configured
            subject = "Verify your account"
            body = f"""
                <p>Hi {getattr(user, 'full_name', '') or 'there'},</p>
                <p>Click to verify your account:</p>
                <p><a href="{verify_url}">{verify_url}</a></p>
            """
            sender.send(to=getattr(user, "email"), subject=subject, html_body=body)

    async def get_user_manager(user_db=Require(get_user_db)):
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
        return JWTStrategy(secret=secret, lifetime_seconds=lifetime)

    bearer_transport = BearerTransport(tokenUrl=f"{public_auth_prefix}/login")
    auth_backend = AuthenticationBackend(
        name="jwt", transport=bearer_transport, get_strategy=get_jwt_strategy
    )
    fastapi_users = FastAPIUsers(get_user_manager, [auth_backend])

    # IMPORTANT: requires_verification=True forces unverified users to be rejected on login.
    auth_router = dualize_router(
        fastapi_users.get_auth_router(auth_backend, requires_verification=True)
    )
    users_router = dualize_router(
        fastapi_users.get_users_router(user_schema_read, user_schema_create, user_schema_update)
    )
    register_router = dualize_router(
        fastapi_users.get_register_router(user_schema_read, user_schema_create)
    )

    # Add verify router (handles GET /verify?token=...)
    verify_router = dualize_router(fastapi_users.get_verify_router(user_schema_read))

    # Return verify_router in the tuple (so add_auth can mount it)
    return (
        fastapi_users,
        auth_backend,
        auth_router,
        users_router,
        get_jwt_strategy,
        register_router,
        verify_router,
    )
