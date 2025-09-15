from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheSettings(BaseSettings):
    cache_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    cache_prefix: str = Field(default="svc")
    cache_default_ttl: int = Field(default=300)
    cache_compress: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_prefix="",  # read REDIS_URL, CACHE_* directly
        case_sensitive=False,
    )

    @property
    def resolved_url(self) -> str:
        if not self.cache_url:
            raise RuntimeError("Missing REDIS_URL (or cache_url).")
        return self.cache_url
