from __future__ import annotations

from typing import Literal, cast

from fastapi import Depends, FastAPI
from starlette.middleware.sessions import SessionMiddleware

from svc_infra.api.fastapi.auth.gaurd import auth_session_router, login_client_gaurd
from svc_infra.api.fastapi.auth.mfa.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.auth.mfa.router import mfa_router
from svc_infra.api.fastapi.auth.routers.account import account_router
from svc_infra.api.fastapi.auth.routers.apikey_router import apikey_router
from svc_infra.api.fastapi.auth.routers.oauth_router import oauth_router_with_backend
from svc_infra.api.fastapi.auth.routers.session_router import build_session_router
from svc_infra.api.fastapi.db.sql.users import get_fastapi_users
from svc_infra.api.fastapi.paths.prefix import AUTH_PREFIX, USER_PREFIX
from svc_infra.app.env import CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV
from svc_infra.db.sql.apikey import bind_apikey_model

from .policy import AuthPolicy, DefaultAuthPolicy
from .providers import providers_from_settings
from .settings import get_auth_settings
from .state import set_auth_state


def install_auth_routers(
    app: FastAPI,
    *,
    auth_prefix: str,
    mfa_router_instance,
    include_in_docs: bool,
    enable_api_keys: bool = False,
    user_model=None,
    apikey_table_name: str = "api_keys",
) -> None:
    """Install routers that use the auth prefix."""
    if enable_api_keys and user_model:
        bind_apikey_model(user_model, table_name=apikey_table_name)
        app.include_router(
            apikey_router(),
            prefix=auth_prefix,
            tags=["API Keys"],
            include_in_schema=include_in_docs,
        )

    # MFA endpoints
    app.include_router(
        mfa_router_instance,
        prefix=auth_prefix,
        tags=["Multi-Factor Authentication"],
        include_in_schema=include_in_docs,
    )


def install_user_routers(
    app: FastAPI,
    *,
    user_prefix: str,
    auth_session_router_instance,
    register_router,
    verify_router,
    reset_router,
    users_router,
    account_router_instance,
    include_in_docs: bool,
) -> None:
    """Install routers that use the user prefix."""
    # Session management
    app.include_router(
        auth_session_router_instance,
        prefix=user_prefix,
        tags=["Session / Registration"],
        include_in_schema=include_in_docs,
        dependencies=[Depends(login_client_gaurd)],
    )
    # Session/device listing & revocation endpoints (AuthSession model)
    # Mounted under the user prefix so final paths become /{user_prefix}/sessions/... (e.g., /users/sessions/me)
    # The router itself has a /sessions prefix.
    app.include_router(
        build_session_router(),
        prefix=user_prefix,
        tags=["Session Management"],
        include_in_schema=include_in_docs,
    )
    app.include_router(
        register_router,
        prefix=user_prefix,
        tags=["Session / Registration"],
        include_in_schema=include_in_docs,
    )
    app.include_router(
        verify_router,
        prefix=user_prefix,
        tags=["Session / Registration"],
        include_in_schema=include_in_docs,
    )
    app.include_router(
        reset_router,
        prefix=user_prefix,
        tags=["Session / Registration"],
        include_in_schema=include_in_docs,
    )

    # Users
    app.include_router(
        users_router,
        prefix=user_prefix,
        tags=["Users"],
        include_in_schema=include_in_docs,
    )

    # Account management
    app.include_router(
        account_router_instance,
        prefix=user_prefix,
        tags=["Account Management"],
        include_in_schema=include_in_docs,
    )


def setup_oauth_authentication(
    app: FastAPI,
    *,
    user_model,
    auth_backend,
    settings_obj,
    auth_prefix: str,
    post_login_redirect: str | None,
    provider_account_model=None,
    auth_policy: AuthPolicy,
    include_in_docs: bool,
) -> None:
    """Set up OAuth authentication if providers are available."""
    providers = providers_from_settings(settings_obj)
    if not providers:
        return

    oauth_router_instance = oauth_router_with_backend(
        user_model=user_model,
        auth_backend=auth_backend,
        providers=providers,
        post_login_redirect=post_login_redirect
        or getattr(settings_obj, "post_login_redirect", "/"),
        provider_account_model=provider_account_model,
        auth_policy=auth_policy,
    )

    # Install oauth prefix routers
    install_oauth_routers(
        app,
        oauth_prefix=auth_prefix + "/oauth",
        oauth_router_instance=oauth_router_instance,
        include_in_docs=include_in_docs,
    )


def setup_password_authentication(
    app: FastAPI,
    *,
    fapi,
    auth_backend,
    user_model,
    get_strategy,
    users_router,
    register_router,
    verify_router,
    reset_router,
    auth_prefix: str,
    user_prefix: str,
    policy: AuthPolicy,
    include_in_docs: bool,
    enable_api_keys: bool,
    apikey_table_name: str,
) -> None:
    """Set up password-based authentication routers."""
    # Create router instances
    auth_session_router_instance = auth_session_router(
        fapi=fapi,
        auth_backend=auth_backend,
        user_model=user_model,
        get_mfa_pre_writer=get_mfa_pre_jwt_writer,
        auth_policy=policy,
    )

    mfa_router_instance = mfa_router(
        user_model=user_model,
        get_strategy=get_strategy,
        fapi=fapi,
    )

    account_router_instance = account_router(user_model=user_model)

    # Install auth prefix routers
    install_auth_routers(
        app,
        auth_prefix=auth_prefix,
        mfa_router_instance=mfa_router_instance,
        include_in_docs=include_in_docs,
        enable_api_keys=enable_api_keys,
        user_model=user_model,
        apikey_table_name=apikey_table_name,
    )

    # Install user prefix routers
    install_user_routers(
        app,
        user_prefix=user_prefix,
        auth_session_router_instance=auth_session_router_instance,
        register_router=register_router,
        verify_router=verify_router,
        reset_router=reset_router,
        users_router=users_router,
        account_router_instance=account_router_instance,
        include_in_docs=include_in_docs,
    )


def install_oauth_routers(
    app: FastAPI,
    *,
    oauth_prefix: str,
    oauth_router_instance,
    include_in_docs: bool,
) -> None:
    """Install routers that use the oauth prefix."""
    app.include_router(
        oauth_router_instance,
        prefix=oauth_prefix,
        tags=["OAuth Authentication"],
        include_in_schema=include_in_docs,
    )


def add_auth_users(
    app: FastAPI,
    *,
    user_model,
    schema_read,
    schema_create,
    schema_update,
    post_login_redirect: str | None = None,
    auth_prefix: str = AUTH_PREFIX,
    user_prefix: str = USER_PREFIX,
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
        setup_password_authentication(
            app,
            fapi=fapi,
            auth_backend=auth_backend,
            user_model=user_model,
            get_strategy=get_strategy,
            users_router=users_router,
            register_router=register_router,
            verify_router=verify_router,
            reset_router=reset_router,
            auth_prefix=auth_prefix,
            user_prefix=user_prefix,
            policy=policy,
            include_in_docs=include_in_docs,
            enable_api_keys=enable_api_keys,
            apikey_table_name=apikey_table_name,
        )

    if enable_oauth:
        setup_oauth_authentication(
            app,
            user_model=user_model,
            auth_backend=auth_backend,
            settings_obj=settings_obj,
            auth_prefix=auth_prefix,
            post_login_redirect=post_login_redirect,
            provider_account_model=provider_account_model,
            auth_policy=policy,
            include_in_docs=include_in_docs,
        )
