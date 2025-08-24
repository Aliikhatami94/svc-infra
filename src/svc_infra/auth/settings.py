from __future__ import annotations
from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    jwt_secret: SecretStr
    jwt_lifetime_seconds: int = 60 * 60 * 24 * 7

    # Baseline optional providers
    google_client_id: Optional[str] = None
    google_client_secret: Optional[SecretStr] = None
    github_client_id: Optional[str] = None
    github_client_secret: Optional[SecretStr] = None

    # Extendable: catch-all for provider-specific extras
    extra_providers: dict[str, dict[str, str]] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")


_settings: AuthSettings | None = None


def get_auth_settings() -> AuthSettings:
    global _settings
    if _settings is None:
        _settings = AuthSettings()
    return _settings

