from fastapi import FastAPI

from svc_infra.api.fastapi.auth import integration
from svc_infra.api.fastapi.dualize import DualAPIRouter


def _make_router(path: str) -> DualAPIRouter:
    router = DualAPIRouter()

    @router.get(path)
    async def _handler():
        return {"ok": True}

    return router


def test_add_auth_without_providers(monkeypatch):
    """When no providers are returned, add_auth should only register the auth and users routers."""
    auth_router = _make_router("/auth_foo")
    users_router = _make_router("/user_me")

    def fake_get_fastapi_users(
        user_model,
        user_schema_read,
        user_schema_create,
        user_schema_update,
        auth_prefix,
    ):
        return ("FAKE_FASTAPI_USERS", "FAKE_BACKEND", auth_router, users_router, None)

    monkeypatch.setattr(integration, "get_fastapi_users", fake_get_fastapi_users)
    monkeypatch.setattr(integration, "providers_from_settings", lambda settings: {})

    app = FastAPI()
    integration.add_auth(
        app,
        user_model=None,
        schema_read=None,
        schema_create=None,
        schema_update=None,
    )

    paths = {r.path for r in app.routes if hasattr(r, "path")}

    # auth and users routers are included under the auth_prefix (default "/auth")
    assert "/auth/auth_foo" in paths
    assert "/auth/user_me" in paths

    # no oauth routes should be registered
    assert not any(p.startswith("/_sql/auth/oauth") for p in paths)


def test_add_auth_with_providers(monkeypatch):
    """When providers exist, add_auth should register the oauth router returned by oauth_router_with_backend."""
    auth_router = _make_router("/auth_foo")
    users_router = _make_router("/user_me")

    def fake_get_fastapi_users(
        user_model,
        user_schema_read,
        user_schema_create,
        user_schema_update,
        auth_prefix,
    ):
        return ("FAKE_FASTAPI_USERS", "FAKE_BACKEND", auth_router, users_router, None)

    def fake_oauth_router_with_backend(
        *, user_model, auth_backend, providers, post_login_redirect, prefix
    ):
        # ensure the auth_backend from get_fastapi_users is passed through
        assert auth_backend == "FAKE_BACKEND"
        router = DualAPIRouter(prefix=prefix)

        @router.get("/callback")
        async def _cb():
            return {"ok": True}

        return router

    monkeypatch.setattr(integration, "get_fastapi_users", fake_get_fastapi_users)
    monkeypatch.setattr(integration, "providers_from_settings", lambda settings: {"google": {}})
    monkeypatch.setattr(integration, "oauth_router_with_backend", fake_oauth_router_with_backend)

    app = FastAPI()
    integration.add_auth(
        app,
        user_model=None,
        schema_read=None,
        schema_create=None,
        schema_update=None,
    )

    paths = {r.path for r in app.routes if hasattr(r, "path")}

    # oauth router should be registered with the prefix passed through (/_sql + default oauth_prefix)
    assert "/_sql/auth/oauth/callback" in paths
