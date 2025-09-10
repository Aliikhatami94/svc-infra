from __future__ import annotations

import importlib
import json
from typing import List

import pytest
from pydantic import SecretStr

from svc_infra.auth.settings import AuthSettings, OIDCProvider, get_auth_settings


def _reset_settings_cache(monkeypatch):
    import svc_infra.auth.settings as settings_mod

    monkeypatch.setattr(settings_mod, "_settings", None, raising=False)


def test_instantiation_allows_missing_jwt(monkeypatch):
    # Ensure no env leaks
    monkeypatch.delenv("AUTH_JWT__SECRET", raising=False)

    # With jwt optional, constructing without env should NOT raise
    s = AuthSettings()
    assert s.jwt is None


def test_env_loading_and_defaults(monkeypatch):
    _reset_settings_cache(monkeypatch)
    # Nested field -> needs double underscore with env_nested_delimiter semantics
    monkeypatch.setenv("AUTH_JWT__SECRET", "sekret")

    s = AuthSettings()

    assert s.jwt is not None
    assert isinstance(s.jwt.secret, SecretStr)
    assert s.jwt.secret.get_secret_value() == "sekret"
    # Default from JWTSettings
    assert s.jwt.lifetime_seconds == 60 * 60 * 24 * 7

    # Optional provider creds default None
    assert s.google_client_id is None
    assert s.google_client_secret is None
    assert s.github_client_id is None
    assert s.github_client_secret is None
    assert s.ms_client_id is None
    assert s.ms_client_secret is None
    assert s.ms_tenant is None
    assert s.li_client_id is None
    assert s.li_client_secret is None

    # Generic OIDC providers default empty list
    assert isinstance(s.oidc_providers, list)
    assert s.oidc_providers == []


def test_constructor_override_works_without_env(monkeypatch):
    monkeypatch.delenv("AUTH_JWT__SECRET", raising=False)

    # Pass nested jwt as a dict (pydantic builds JWTSettings)
    s = AuthSettings(jwt={"secret": "abc"})

    assert s.jwt is not None
    assert s.jwt.secret.get_secret_value() == "abc"
    assert s.jwt.lifetime_seconds == 60 * 60 * 24 * 7


def test_oidc_providers_parse_from_env_json_with_default_scope(monkeypatch):
    _reset_settings_cache(monkeypatch)

    providers_env: List[dict] = [
        {
            "name": "okta",
            "issuer": "https://okta.example.com/",
            "client_id": "okta-id",
            "client_secret": "okta-secret",
            # scope omitted -> default
        },
        {
            "name": "auth0",
            "issuer": "https://example.auth0.com",
            "client_id": "auth0-id",
            "client_secret": "auth0-secret",
            "scope": "openid email",
        },
    ]

    # Provide jwt via nested env var
    monkeypatch.setenv("AUTH_JWT__SECRET", "sekret")
    monkeypatch.setenv("AUTH_OIDC_PROVIDERS", json.dumps(providers_env))

    s = AuthSettings()

    assert len(s.oidc_providers) == 2
    okta = next(p for p in s.oidc_providers if p.name == "okta")
    auth0 = next(p for p in s.oidc_providers if p.name == "auth0")

    assert isinstance(okta, OIDCProvider)
    assert okta.issuer == "https://okta.example.com/"  # unchanged here; providers layer trims later
    assert okta.client_id == "okta-id"
    assert okta.client_secret.get_secret_value() == "okta-secret"
    assert okta.scope == "openid email profile"  # defaulted by model

    assert isinstance(auth0.client_secret, SecretStr)
    assert auth0.scope == "openid email"


def test_get_auth_settings_singleton_and_env_cache(monkeypatch):
    _reset_settings_cache(monkeypatch)

    # First load with secret ONE (nested env)
    monkeypatch.setenv("AUTH_JWT__SECRET", "one")
    s1 = get_auth_settings()
    assert s1.jwt is not None
    assert s1.jwt.secret.get_secret_value() == "one"

    # Change env, but cached instance should remain
    monkeypatch.setenv("AUTH_JWT__SECRET", "two")
    s2 = get_auth_settings()
    assert s2 is s1
    assert s2.jwt.secret.get_secret_value() == "one"

    # Reset cache and re-import to simulate fresh process
    _reset_settings_cache(monkeypatch)
    import svc_infra.auth.settings as settings_mod

    importlib.reload(settings_mod)

    # Now get fresh settings; should reflect new env
    from svc_infra.auth.settings import get_auth_settings as fresh_get

    s3 = fresh_get()
    assert s3.jwt is not None
    assert s3.jwt.secret.get_secret_value() == "two"
