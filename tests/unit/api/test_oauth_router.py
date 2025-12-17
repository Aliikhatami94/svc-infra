"""Tests for the OAuth router success flow."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from svc_infra.api.fastapi.auth.routers import oauth_router as oauth_router_module
from svc_infra.api.fastapi.auth.routers.oauth_router import oauth_router_with_backend
from tests.unit.utils.test_helpers import setup_database_mocks


@pytest.mark.asyncio
async def test_oauth_callback_success_returns_redirect_with_cookies(monkeypatch):
    """The OAuth callback should return a redirect response with cookies set."""

    # Stub out the OAuth client so we don't need real provider interactions.
    class DummyClient:
        async def authorize_access_token(
            self, *args, **kwargs
        ):  # pragma: no cover - patched
            return {"access_token": "token"}

    class DummyOAuth:
        def __init__(self):
            self._client = DummyClient()

        def register(self, *args, **kwargs):  # pragma: no cover - router setup only
            return None

        def create_client(self, provider: str) -> DummyClient:
            assert provider == "test"
            return self._client

    monkeypatch.setattr(oauth_router_module, "OAuth", lambda: DummyOAuth())

    # Patch internal helpers to focus solely on the success flow.
    async def fake_validate_oauth_state(request, provider):
        return None, None

    async def fake_exchange_code_for_token(client, request, verifier, provider):
        return {"access_token": "stub"}

    async def fake_extract_user_info(request, client, token, provider, cfg, nonce):
        return ("user@example.com", "User", "provider-id", True, {})

    user = SimpleNamespace(
        id="user-id", is_active=True, tenant_id=None, last_login=None
    )

    async def fake_process_user_authentication(
        session,
        user_model,
        provider_account_model,
        provider,
        email,
        full_name,
        provider_user_id,
        token,
        raw_claims,
    ):
        return user

    def fake_determine_redirect(request, provider, post_login_redirect):
        return "https://app.example.com/welcome"

    async def fake_handle_mfa(policy, user, redirect_url):
        return None

    async def fake_issue_session_and_refresh(
        session, user_id, tenant_id, user_agent, ip_hash
    ):
        return "refresh-token", SimpleNamespace(id="refresh-id")

    async def fake_set_cookie_on_response(resp, auth_backend, user, *, refresh_raw):
        resp.set_cookie("auth-cookie", "jwt-token")
        resp.set_cookie("refresh-cookie", refresh_raw)

    def fake_clean_state(request, provider):  # pragma: no cover - trivial
        return None

    monkeypatch.setattr(
        oauth_router_module, "_validate_oauth_state", fake_validate_oauth_state
    )
    monkeypatch.setattr(
        oauth_router_module, "_exchange_code_for_token", fake_exchange_code_for_token
    )
    monkeypatch.setattr(
        oauth_router_module, "_extract_user_info_from_provider", fake_extract_user_info
    )
    monkeypatch.setattr(
        oauth_router_module,
        "_process_user_authentication",
        fake_process_user_authentication,
    )
    monkeypatch.setattr(
        oauth_router_module, "_determine_final_redirect_url", fake_determine_redirect
    )
    monkeypatch.setattr(oauth_router_module, "_handle_mfa_redirect", fake_handle_mfa)
    monkeypatch.setattr(
        oauth_router_module, "issue_session_and_refresh", fake_issue_session_and_refresh
    )
    monkeypatch.setattr(
        oauth_router_module, "_set_cookie_on_response", fake_set_cookie_on_response
    )
    monkeypatch.setattr(
        oauth_router_module, "_clean_oauth_session_state", fake_clean_state
    )

    class DummyPolicy:
        def __init__(self):
            self.success_called = False

        async def should_require_mfa(self, user):
            return False

        async def on_login_success(self, user):
            self.success_called = True

    class DummyStrategy:
        async def write_token(self, user):
            return "jwt-token"

    class DummyBackend:
        def get_strategy(self):
            return DummyStrategy()

    policy = DummyPolicy()

    router = oauth_router_with_backend(
        user_model=object,
        auth_backend=DummyBackend(),
        providers={
            "test": {
                "kind": "oidc",
                "client_id": "cid",
                "client_secret": "secret",
                "issuer": "https://issuer.example.com",
            }
        },
        post_login_redirect="/",
        auth_policy=policy,
    )

    app = FastAPI()
    setup_database_mocks(app)
    app.include_router(router, prefix="/oauth")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/oauth/test/callback?code=abc")

    assert response.status_code == 302
    # Cross-origin redirect appends token as URL fragment for client-side extraction
    assert (
        response.headers["location"]
        == "https://app.example.com/welcome#access_token=jwt-token"
    )
    assert response.cookies.get("auth-cookie") == "jwt-token"
    assert response.cookies.get("refresh-cookie") == "refresh-token"
    assert policy.success_called is True
    assert user.last_login is not None
