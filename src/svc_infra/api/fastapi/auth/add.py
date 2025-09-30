from __future__ import annotations

from typing import Literal, cast

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from svc_infra.api.fastapi.auth.gaurd import auth_session_router, login_client_guard
from svc_infra.api.fastapi.auth.mfa.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.auth.mfa.router import mfa_router
from svc_infra.api.fastapi.auth.routers.account import account_router
from svc_infra.api.fastapi.auth.routers.apikey_router import apikey_router
from svc_infra.api.fastapi.auth.routers.oauth_router import oauth_router_with_backend
from svc_infra.api.fastapi.db.sql.users import get_fastapi_users
from svc_infra.app.env import CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV
from svc_infra.db.sql.apikey import bind_apikey_model

from .. import Require
from .policy import AuthPolicy, DefaultAuthPolicy
from .providers import providers_from_settings
from .settings import get_auth_settings
from .state import set_auth_state


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
    enable_api_keys: bool = False,
    apikey_table_name: str = "api_keys",
    provider_account_model=None,
    auth_policy: AuthPolicy | None = None,
) -> None:
    (
        fapi,
        auth_backend,
        auth_router,
        users_router,
        get_strategy,
        register_router,
        verify_router,
        reset_router,
    ) = get_fastapi_users(
        user_model=user_model,
        user_schema_read=schema_read,
        user_schema_create=schema_create,
        user_schema_update=schema_update,
        public_auth_prefix=auth_prefix,
    )

    # Make the boot-time strategy and model available to resolvers
    set_auth_state(user_model=user_model, get_strategy=get_strategy, auth_prefix=auth_prefix)

    settings_obj = get_auth_settings()
    policy = auth_policy or DefaultAuthPolicy(settings_obj)
    include_in_docs = CURRENT_ENVIRONMENT in (LOCAL_ENV, DEV_ENV)

    if not any(m.cls.__name__ == "SessionMiddleware" for m in app.user_middleware):
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

    if enable_password:
        # Bind + mount (optional) API keys BEFORE adding the keys router
        if enable_api_keys:
            bind_apikey_model(user_model, table_name=apikey_table_name)
            app.include_router(apikey_router(), include_in_schema=include_in_docs)

        # Auth session endpoints (login/logout)
        app.include_router(
            auth_session_router(
                fapi=fapi,
                auth_backend=auth_backend,
                user_model=user_model,
                get_mfa_pre_writer=get_mfa_pre_jwt_writer,
                public_auth_prefix=auth_prefix,
                auth_policy=policy,
            ),
            include_in_schema=include_in_docs,
            dependencies=[Require(login_client_guard)],
        )

        # Users & auth management
        app.include_router(
            users_router,
            prefix=auth_prefix,
            tags=["users"],
            include_in_schema=include_in_docs,
        )
        app.include_router(
            register_router,
            prefix=auth_prefix,
            tags=["auth"],
            include_in_schema=include_in_docs,
        )
        app.include_router(
            verify_router,
            prefix=auth_prefix,
            tags=["auth"],
            include_in_schema=include_in_docs,
        )
        app.include_router(
            reset_router,
            prefix=auth_prefix,
            tags=["auth"],
            include_in_schema=include_in_docs,
        )

        # MFA endpoints
        app.include_router(
            mfa_router(
                user_model=user_model,
                get_strategy=get_strategy,
                fapi=fapi,
                auth_prefix=auth_prefix,
            ),
            include_in_schema=include_in_docs,
        )

        # Account management
        app.include_router(
            account_router(user_model=user_model, auth_prefix=auth_prefix),
            include_in_schema=include_in_docs,
        )

    if enable_oauth:
        providers = providers_from_settings(settings_obj)
        if providers:
            app.include_router(
                oauth_router_with_backend(
                    user_model=user_model,
                    auth_backend=auth_backend,
                    providers=providers,
                    post_login_redirect=post_login_redirect
                    or getattr(settings_obj, "post_login_redirect", "/"),
                    prefix=oauth_prefix,
                    provider_account_model=provider_account_model,
                    auth_policy=policy,
                ),
                include_in_schema=include_in_docs,
            )
