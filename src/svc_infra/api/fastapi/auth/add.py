from __future__ import annotations

from typing import Literal, cast

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from svc_infra.api.fastapi.db.sql.users import get_fastapi_users
from svc_infra.app.env import CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV

from .oauth_router import oauth_router_with_backend
from .providers import providers_from_settings
from .settings import get_auth_settings


def add_auth(
    app: FastAPI,
    *,
    user_model,
    schema_read,
    schema_create,
    schema_update,
    post_login_redirect: str | None = None,
    auth_prefix: str = "/auth",
    oauth_prefix: str = "/auth/oauth",
    enable_password: bool = True,
    enable_oauth: bool = True,
    provider_account_model=None,
) -> None:
    """
    Wire auth into the app.

    - Password login (/auth/jwt/*, /auth/users/*) is optional via enable_password.
    - OAuth providers (/auth/oauth/*) are optional via enable_oauth.
    """
    fapi, auth_backend, auth_router, users_router, _, register_router = get_fastapi_users(
        user_model=user_model,
        user_schema_read=schema_read,
        user_schema_create=schema_create,
        user_schema_update=schema_update,
        public_auth_prefix=auth_prefix,
        login_path="/jwt/login",
    )

    # ---- settings & session middleware (for OAuth round-trip + cookie) & docs ----
    settings_obj = get_auth_settings()
    include_in_docs = CURRENT_ENVIRONMENT in (LOCAL_ENV, DEV_ENV)

    # ensure SessionMiddleware mounted exactly once
    if not any(m.cls.__name__ == "SessionMiddleware" for m in app.user_middleware):
        # Use JWT secret as session secret fallback
        jwt_block = getattr(settings_obj, "jwt", None)
        secret = (
            jwt_block.secret.get_secret_value()
            if jwt_block and getattr(jwt_block, "secret", None)
            else "svc-dev-secret-change-me"
        )
        same_site_lit = cast(
            Literal["lax", "strict", "none"],
            str(getattr(settings_obj, "session_cookie_samesite", "lax")).lower(),
        )
        app.add_middleware(
            SessionMiddleware,
            secret_key=secret,
            session_cookie=getattr(settings_obj, "session_cookie_name", "svc_session"),
            max_age=getattr(settings_obj, "session_cookie_max_age_seconds", 4 * 3600),
            same_site=same_site_lit,
            https_only=bool(getattr(settings_obj, "session_cookie_secure", False)),
        )

    # ---- Conditionally mount password-based auth ----
    if enable_password:
        app.include_router(
            auth_router, prefix=auth_prefix, tags=["auth"], include_in_schema=include_in_docs
        )
        app.include_router(
            users_router, prefix=auth_prefix, tags=["users"], include_in_schema=include_in_docs
        )
        app.include_router(
            register_router, prefix=auth_prefix, tags=["auth"], include_in_schema=include_in_docs
        )

    # ---- Conditionally mount OAuth providers ----
    if enable_oauth:
        providers = providers_from_settings(settings_obj)
        if providers:
            app.include_router(
                oauth_router_with_backend(
                    user_model=user_model,
                    auth_backend=auth_backend,
                    providers=providers_from_settings(settings_obj),
                    post_login_redirect=post_login_redirect
                    or getattr(settings_obj, "post_login_redirect", "/"),
                    prefix=oauth_prefix,
                    provider_account_model=provider_account_model,
                ),
                include_in_schema=include_in_docs,
            )
