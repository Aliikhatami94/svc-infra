from __future__ import annotations

from functools import cached_property

from pydantic import BaseSettings, Field


class CacheSettings(BaseSettings):
    cache_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    cache_prefix: str = Field(default="svc")
    cache_default_ttl: int = Field(default=300)  # seconds
    cache_compress: bool = Field(default=False)

    class Config:
        env_prefix = ""  # read REDIS_URL, CACHE_* directly
        case_sensitive = False

    @cached_property
    def resolved_url(self) -> str:
        if not self.cache_url:
            raise RuntimeError("Missing REDIS_URL (or cache_url).")
        return self.cache_url
