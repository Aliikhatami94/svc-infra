from __future__ import annotations

import json
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OIDCProvider(BaseModel):
    name: str
    issuer: str
    client_id: str
    client_secret: SecretStr
    scope: str = "openid email profile"


class JWTSettings(BaseModel):
    secret: SecretStr
    lifetime_seconds: int = 60 * 60 * 24 * 7


class AuthSettings(BaseSettings):
    # ---- JWT ----
    jwt: Optional[JWTSettings] = None

    # ---- Built-in provider creds (all optional) ----
    google_client_id: Optional[str] = None
    google_client_secret: Optional[SecretStr] = None

    github_client_id: Optional[str] = None
    github_client_secret: Optional[SecretStr] = None

    ms_client_id: Optional[str] = None
    ms_client_secret: Optional[SecretStr] = None
    ms_tenant: Optional[str] = None

    li_client_id: Optional[str] = None
    li_client_secret: Optional[SecretStr] = None

    oidc_providers: List[OIDCProvider] = Field(default_factory=list)

    # ---- Redirect + cookie settings ----
    post_login_redirect: AnyHttpUrl | str = "http://localhost:3000/app"

    # NOTE: keep as raw string to avoid pydantic JSON parsing at env stage.
    # Accepts either JSON (["a","b"]) or comma-separated ("a,b").
    redirect_allow_hosts_raw: str = "localhost,127.0.0.1"

    session_cookie_name: str = "svc_session"  # Starlette session
    auth_cookie_name: str = "svc_auth"  # JWT cookie
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_cookie_domain: Optional[str] = None
    session_cookie_max_age_seconds: int = 60 * 60 * 4

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
    )


_settings: AuthSettings | None = None


def get_auth_settings() -> AuthSettings:
    global _settings
    if _settings is None:
        _settings = AuthSettings()
    return _settings


def parse_redirect_allow_hosts(raw: str | None) -> list[str]:
    """Parse JSON list or comma-separated hosts into a list of strings."""
    if not raw:
        return ["localhost", "127.0.0.1"]
    s = raw.strip()
    # Try JSON first
    if s.startswith("["):
        try:
            val = json.loads(s)
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
        except Exception:
            pass
    # Fallback: comma-separated
    return [h.strip() for h in s.split(",") if h.strip()]
