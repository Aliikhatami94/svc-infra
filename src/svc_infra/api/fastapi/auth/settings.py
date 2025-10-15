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
    # Optional older secrets accepted for verification during rotation window
    old_secrets: List[SecretStr] = Field(default_factory=list)


class PasswordClient(BaseModel):
    client_id: str
    client_secret: SecretStr


class AuthSettings(BaseSettings):
    # ---- JWT ----
    jwt: Optional[JWTSettings] = None

    # ---- Password login ----
    password_clients: List[PasswordClient] = Field(default_factory=list)
    require_client_secret_on_password_login: bool = False

    # ---- MFA / TOTP ----
    mfa_default_enabled_for_new_users: bool = False
    mfa_enforce_for_all_users: bool = False
    mfa_enforce_for_tenants: list[str] = []
    mfa_issuer: str = "svc-infra"
    mfa_pre_token_lifetime_seconds: int = 300
    mfa_recovery_codes: int = 8
    mfa_recovery_code_length: int = 10

    # ---- Email OTP ----
    email_otp_ttl_seconds: int = 5 * 60
    email_otp_cooldown_seconds: int = 60
    email_otp_attempts: int = 5

    # ---- Email/SMTP (verification, reset, etc.) ----
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[SecretStr] = None
    smtp_from: Optional[str] = None

    # Dev convenience: auto-verify users without sending email
    auto_verify_in_dev: bool = True

    # ---- Built-in provider creds (optional) ----
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
    redirect_allow_hosts_raw: str = "localhost,127.0.0.1"

    session_cookie_name: str = "svc_session"
    auth_cookie_name: str = "svc_auth"
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
    if not raw:
        return ["localhost", "127.0.0.1"]
    s = raw.strip()
    if s.startswith("["):
        try:
            val = json.loads(s)
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
        except Exception:
            pass
    return [h.strip() for h in s.split(",") if h.strip()]
