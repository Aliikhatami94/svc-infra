from __future__ import annotations
from typing import Any

from pydantic import SecretStr

from svc_infra.auth.providers import providers_from_settings


class Dummy:
    pass


def _settings(**kwargs: Any):
    s = Dummy()
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


def test_empty_settings_returns_empty():
    s = _settings()
    reg = providers_from_settings(s)
    assert reg == {}


def test_google_provider_included_with_values():
    s = _settings(google_client_id="gid", google_client_secret=SecretStr("gsecret"))
    reg = providers_from_settings(s)
    assert set(reg.keys()) == {"google"}
    g = reg["google"]
    assert g["kind"] == "oidc"
    assert g["issuer"] == "https://accounts.google.com"
    assert g["client_id"] == "gid"
    assert g["client_secret"] == "gsecret"
    assert g["scope"] == "openid email profile"


def test_github_provider_included_with_urls_and_scope():
    s = _settings(github_client_id="ghid", github_client_secret=SecretStr("ghsecret"))
    reg = providers_from_settings(s)
    gh = reg["github"]
    assert gh["kind"] == "github"
    assert gh["authorize_url"] == "https://github.com/login/oauth/authorize"
    assert gh["access_token_url"] == "https://github.com/login/oauth/access_token"
    assert gh["api_base_url"] == "https://api.github.com/"
    assert gh["client_id"] == "ghid"
    assert gh["client_secret"] == "ghsecret"
    assert gh["scope"] == "user:email"


def test_microsoft_provider_uses_tenant_in_issuer():
    s = _settings(ms_client_id="mid", ms_client_secret=SecretStr("msecret"), ms_tenant="contoso")
    reg = providers_from_settings(s)
    ms = reg["microsoft"]
    assert ms["kind"] == "oidc"
    assert ms["issuer"] == "https://login.microsoftonline.com/contoso/v2.0"
    assert ms["client_id"] == "mid"
    assert ms["client_secret"] == "msecret"
    assert ms["scope"] == "openid email profile"


def test_linkedin_provider_included_with_urls_and_scope():
    s = _settings(li_client_id="lid", li_client_secret=SecretStr("lsecret"))
    reg = providers_from_settings(s)
    li = reg["linkedin"]
    assert li["kind"] == "linkedin"
    assert li["authorize_url"] == "https://www.linkedin.com/oauth/v2/authorization"
    assert li["access_token_url"] == "https://www.linkedin.com/oauth/v2/accessToken"
    assert li["api_base_url"] == "https://api.linkedin.com/v2/"
    assert li["client_id"] == "lid"
    assert li["client_secret"] == "lsecret"
    assert li["scope"] == "r_liteprofile r_emailaddress"


def test_generic_oidc_providers_list_with_default_scope_and_rstrip():
    class OIDCItem:
        def __init__(self, name: str, issuer: str, client_id: str, client_secret: SecretStr, scope: str | None = None):
            self.name = name
            self.issuer = issuer
            self.client_id = client_id
            self.client_secret = client_secret
            self.scope = scope

    items = [
        OIDCItem("okta", "https://okta.example.com/", "okta-id", SecretStr("okta-secret"), None),
        OIDCItem("auth0", "https://example.auth0.com", "auth0-id", SecretStr("auth0-secret"), "openid email"),
    ]
    s = _settings(oidc_providers=items)
    reg = providers_from_settings(s)

    ok = reg["okta"]
    assert ok["kind"] == "oidc"
    assert ok["issuer"] == "https://okta.example.com"  # rstrip('/')</n    assert ok["client_id"] == "okta-id"
    assert ok["client_secret"] == "okta-secret"
    assert ok["scope"] == "openid email profile"  # default

    a0 = reg["auth0"]
    assert a0["kind"] == "oidc"
    assert a0["issuer"] == "https://example.auth0.com"
    assert a0["client_id"] == "auth0-id"
    assert a0["client_secret"] == "auth0-secret"
    assert a0["scope"] == "openid email"


def test_missing_pairs_skip_providers():
    # missing secret -> not included
    s = _settings(google_client_id="gid")
    reg = providers_from_settings(s)
    assert "google" not in reg

    # missing id -> not included
    s2 = _settings(github_client_secret=SecretStr("sec"))
    reg2 = providers_from_settings(s2)
    assert "github" not in reg2

