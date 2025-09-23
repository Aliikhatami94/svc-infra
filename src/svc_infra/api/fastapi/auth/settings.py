from __future__ import annotations

import json
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OIDCProvider(BaseModel):
    name: str
    issuer: str
    client_id: str
    client_secret: SecretStr
    scope: str = "openid email profile"


class JWTSettings(BaseModel):
    secret: SecretStr
    lifetime_seconds: int = 60 * 60 * 24 * 7  # 7d


class AuthSettings(BaseSettings):
    # ---- JWT ----
    jwt: Optional[JWTSettings] = None

    # ---- Built-in provider creds (all optional) ----
    google_client_id: Optional[str] = None
    google_client_secret: Optional[SecretStr] = None

    github_client_id: Optional[str] = None
    github_client_secret: Optional[SecretStr] = None

    # Microsoft Entra ID (Azure AD)
    ms_client_id: Optional[str] = None
    ms_client_secret: Optional[SecretStr] = None
    ms_tenant: Optional[str] = None

    # LinkedIn (non-OIDC)
    li_client_id: Optional[str] = None
    li_client_secret: Optional[SecretStr] = None

    # Generic OIDC providers
    oidc_providers: List[OIDCProvider] = Field(default_factory=list)

    # ---- Redirect + cookie settings ----
    post_login_redirect: AnyHttpUrl | str = "http://localhost:3000/app"
    redirect_allow_hosts: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])

    session_cookie_name: str = "svc_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"  # "lax" | "strict" | "none"
    session_cookie_domain: Optional[str] = None
    session_cookie_max_age_seconds: int = 60 * 60 * 4  # 4h

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
    )

    @field_validator("redirect_allow_hosts", mode="before")
    @classmethod
    def _coerce_redirect_hosts(cls, v):
        if v is None or v == "":
            return ["localhost", "127.0.0.1"]
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, str):
            s = v.strip()
            # Try JSON first
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
            # Fallback: comma/space separated
            return [h.strip() for h in s.split(",") if h.strip()]
        return v


_settings: AuthSettings | None = None


def get_auth_settings() -> AuthSettings:
    global _settings
    if _settings is None:
        _settings = AuthSettings()
    return _settings
