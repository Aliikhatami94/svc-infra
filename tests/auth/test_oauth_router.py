from __future__ import annotations
from typing import Any, Dict, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.auth import oauth_router as oauth_router_module
from svc_infra.auth.oauth_router import oauth_router_with_backend
from svc_infra.api.fastapi.db.integration import get_session


class FakeAuthStrategy:
    def write_token(self, user):
        return "jwt123"


class FakeAuthBackend:
    def __init__(self):
        self.get_strategy = lambda: FakeAuthStrategy()


class FakeUser:
    def __init__(self, email: str, is_active=True, is_superuser=False, is_verified=True):
        self.email = email
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.is_verified = is_verified
        self.hashed_password = None
        self.full_name = None


class Query:
    def __init__(self, model):
        self.model = model
        self.filters: Dict[str, Any] = {}

    def filter_by(self, **kwargs):
        self.filters.update(kwargs)
        return self


class FakeSelect:
    def __call__(self, model):
        return Query(model)


class FakeResult:
    def __init__(self, user: Optional[FakeUser]):
        self._user = user

    class _Scalar:
        def __init__(self, user):
            self._user = user

        def first(self):
            return self._user

    def scalars(self):
        return FakeResult._Scalar(self._user)


class FakeSession:
    def __init__(self):
        # simple in-memory store by email
        self.users: Dict[str, FakeUser] = {}
        self.added = []
        self.flush_count = 0
        self.commits = 0
        self.rollbacks = 0

    # SQLAlchemy AsyncSession compatibility (awaitables)
    async def execute(self, query: Query):
        email = query.filters.get("email")
        user = self.users.get(email)
        return FakeResult(user)

    def add(self, user: FakeUser):
        self.users[user.email] = user
        self.added.append(user)

    async def flush(self):
        self.flush_count += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeResponse:
    def __init__(self, json_data: Any, status_code: int = 200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json


class FakeClient:
    def __init__(self, kind: str, profile: Dict[str, Any] | None = None, emails: list[Dict[str, Any]] | None = None,
                 oidc_userinfo: Dict[str, Any] | None = None):
        self.kind = kind
        self.profile = profile or {}
        self.emails = emails or []
        self.oidc_userinfo = oidc_userinfo

    async def authorize_redirect(self, request, redirect_uri: str):
        # simulate redirect to provider auth endpoint
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=f"https://provider.example/authorize?redirect_uri={redirect_uri}")

    async def authorize_access_token(self, request):
        # return a token object. For OIDC, embed userinfo if provided
        token: Dict[str, Any] = {"access_token": "fake-token"}
        if self.kind == "oidc" and self.oidc_userinfo is not None:
            token["userinfo"] = self.oidc_userinfo
        return token

    async def parse_id_token(self, request, token):
        # fallback path for OIDC if userinfo not present in token
        return self.oidc_userinfo or {}

    async def get(self, path: str, token: Dict[str, Any]):
        # emulate GitHub/LinkedIn API responses
        if self.kind == "github":
            if path == "user":
                return FakeResponse(self.profile)
            if path == "user/emails":
                return FakeResponse(self.emails)
        if self.kind == "linkedin":
            if path == "me":
                return FakeResponse(self.profile)
            if path.startswith("emailAddress"):
                return FakeResponse({"elements": self.emails})
        return FakeResponse({}, status_code=404)


class FakeOAuth:
    def __init__(self):
        self._registered: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, *args, **kwargs):
        # keep what the app registered for potential inspection
        self._registered[name] = kwargs

    def create_client(self, provider: str):
        # Only return a client if the provider was registered
        if provider not in self._registered:
            return None
        # Read provider-specific test data if present
        test_cfg = getattr(oauth_router_module, "_TEST_PROVIDERS", {}).get(provider, {})
        kind = test_cfg.get("kind") or provider
        return FakeClient(
            kind=kind,
            profile=test_cfg.get("_profile"),
            emails=test_cfg.get("_emails"),
            oidc_userinfo=test_cfg.get("_userinfo"),
        )


class FakePasswordHelper:
    def hash(self, value: str) -> str:
        return f"hashed:{value}"


@pytest.fixture(autouse=True)
def patch_oauth_and_select(monkeypatch):
    # Patch OAuth class used inside oauth_router_with_backend
    monkeypatch.setattr(oauth_router_module, "OAuth", FakeOAuth)
    # Patch select used inside the router to our simple Query builder
    monkeypatch.setattr(oauth_router_module, "select", FakeSelect())
    # Patch PasswordHelper to avoid heavy hashing deps
    monkeypatch.setattr(oauth_router_module, "PasswordHelper", lambda: FakePasswordHelper())


@pytest.fixture()
def app_and_session(monkeypatch):
    app = FastAPI()
    session = FakeSession()

    async def _override_get_session():
        try:
            yield session
        finally:
            # mimic integration: commit at end
            await session.commit()

    app.dependency_overrides[get_session] = _override_get_session
    return app, session


def mount_router(app: FastAPI, providers: Dict[str, Dict[str, Any]], post_login_redirect: str = "/done"):
    # expose test providers so FakeOAuth can build FakeClient with extra test data
    oauth_router_module._TEST_PROVIDERS = providers
    backend = FakeAuthBackend()
    router = oauth_router_with_backend(
        user_model=FakeUser,
        auth_backend=backend,
        providers=providers,
        post_login_redirect=post_login_redirect,
        prefix="/oauth",
    )
    app.include_router(router)


def test_login_redirect_for_configured_provider(app_and_session):
    app, _ = app_and_session
    providers = {
        "google": {"kind": "oidc", "client_id": "x", "client_secret": "y", "issuer": "https://accounts.example", "scope": "openid email profile", "_userinfo": {"email": "u@example.com", "name": "User"}},
    }
    mount_router(app, providers)

    client = TestClient(app)
    resp = client.get("/oauth/google/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers.get("location").startswith("https://provider.example/authorize?")


def test_callback_oidc_creates_user_and_redirects(app_and_session):
    app, session = app_and_session
    providers = {
        "google": {"kind": "oidc", "client_id": "x", "client_secret": "y", "issuer": "https://accounts.example", "_userinfo": {"email": "oidc@example.com", "name": "OIDC User"}},
    }
    mount_router(app, providers)

    client = TestClient(app)
    resp = client.get("/oauth/google/callback", follow_redirects=False)
    assert resp.status_code in (302, 307)
    loc = resp.headers.get("location")
    assert loc.startswith("/done?token=") and loc.endswith("jwt123")

    # user persisted with hashed_password and full_name
    user = session.users.get("oidc@example.com")
    assert user is not None
    assert user.full_name == "OIDC User"
    assert user.hashed_password == "hashed:!oauth!"


def test_callback_github_fetches_primary_email(app_and_session):
    app, session = app_and_session
    providers = {
        "github": {
            "kind": "github",
            "client_id": "id",
            "client_secret": "sec",
            "authorize_url": "https://github.com/login/oauth/authorize",
            "access_token_url": "https://github.com/login/oauth/access_token",
            "api_base_url": "https://api.github.com/",
            # simulate missing email in profile and a list of emails with a primary
            "_profile": {"login": "octo", "name": "Octo Cat", "email": None},
            "_emails": [
                {"email": "alt@example.com", "primary": False},
                {"email": "primary@example.com", "primary": True},
            ],
        }
    }
    mount_router(app, providers)

    client = TestClient(app)
    resp = client.get("/oauth/github/callback", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert session.users.get("primary@example.com") is not None


def test_callback_linkedin_extracts_email_and_name(app_and_session):
    app, session = app_and_session
    providers = {
        "linkedin": {
            "kind": "linkedin",
            "client_id": "id",
            "client_secret": "sec",
            "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
            "access_token_url": "https://www.linkedin.com/oauth/v2/accessToken",
            "api_base_url": "https://api.linkedin.com/v2/",
            "_profile": {
                "firstName": {"localized": {"en_US": "Lin"}},
                "lastName": {"localized": {"en_US": "KedIn"}},
            },
            "_emails": [
                {"handle~": {"emailAddress": "lin@example.com"}}
            ],
        }
    }
    mount_router(app, providers)

    client = TestClient(app)
    resp = client.get("/oauth/linkedin/callback", follow_redirects=False)
    assert resp.status_code in (302, 307)
    u = session.users.get("lin@example.com")
    assert u is not None
    assert u.full_name == "Lin KedIn"


def test_callback_missing_email_returns_400(app_and_session):
    app, _ = app_and_session
    providers = {
        "github": {
            "kind": "github",
            "client_id": "id",
            "client_secret": "sec",
            "authorize_url": "https://github.com/login/oauth/authorize",
            "access_token_url": "https://github.com/login/oauth/access_token",
            "api_base_url": "https://api.github.com/",
            # no email in profile or emails list
            "_profile": {"login": "octo", "name": "Octo Cat", "email": None},
            "_emails": [],
        }
    }
    mount_router(app, providers)

    client = TestClient(app)
    resp = client.get("/oauth/github/callback", follow_redirects=False)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No email from provider"
