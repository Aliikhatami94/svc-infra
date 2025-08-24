from __future__ import annotations
from fastapi import FastAPI
from .users import get_fastapi_users
from .oauth_router import oauth_router_with_backend
from .providers import providers_from_settings

from .settings import get_auth_settings

auth_settings = get_auth_settings()

def include_auth(
        app: FastAPI,
        *,
        user_model,
        schema_read,
        schema_create,
        schema_update,
        post_login_redirect: str = "/",
        auth_prefix: str = "/auth",
        oauth_prefix: str = "/auth/oauth",
) -> None:
    fastapi_users, auth_backend, auth_router, users_router, _ = get_fastapi_users(
        user_model=user_model,
        user_schema_read=schema_read,
        user_schema_create=schema_create,
        user_schema_update=schema_update,
        auth_prefix="/_db" + auth_prefix,
    )

    app.include_router(auth_router, prefix=auth_prefix, tags=["auth"])
    app.include_router(users_router, prefix=auth_prefix, tags=["users"])

    providers = providers_from_settings(auth_settings)
    if providers:
        app.include_router(
            oauth_router_with_backend(
                user_model=user_model,
                auth_backend=auth_backend,
                providers=providers,
                post_login_redirect=post_login_redirect,
                prefix="/_db" + oauth_prefix,
            )
        )