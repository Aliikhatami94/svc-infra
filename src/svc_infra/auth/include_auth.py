from __future__ import annotations
from fastapi import FastAPI

from .users import get_fastapi_users
from .oauth_router import oauth_router


def include_auth(
    app: FastAPI,
    *,
    user_model,
    schema_read,
    schema_create,
    schema_update,
    auth_settings,
    post_login_redirect: str = "/",
    auth_prefix: str = "/auth",
    oauth_prefix: str = "/auth/oauth",
) -> None:
    """Compose and mount auth + user routers, and the OAuth router.

    This wires FastAPI Users with the provided schemas and model, and mounts:
    - JWT auth routes under auth_prefix
    - Users CRUD routes under auth_prefix
    - OAuth routes under oauth_prefix (if providers are configured via env)
    """

    fastapi_users, auth_backend, auth_router, users_router, get_jwt_strategy = get_fastapi_users(
        user_model=user_model,
        user_schema_read=schema_read,
        user_schema_create=schema_create,
        user_schema_update=schema_update,
        auth_settings=auth_settings,
        auth_prefix=auth_prefix,
    )

    app.include_router(auth_router, prefix=auth_prefix, tags=["auth"])
    app.include_router(users_router, prefix=auth_prefix, tags=["users"])

    app.include_router(
        oauth_router(
            user_model=user_model,
            jwt_strategy=get_jwt_strategy(),
            post_login_redirect=post_login_redirect,
            settings=auth_settings,
            prefix=oauth_prefix,
        )
    )