from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    """
    Database settings.

    Env support:
      - Prefer DB_* variables (consistent with app settings):
          DB_DATABASE_URL, DB_ECHO, DB_POOL_SIZE, DB_MAX_OVERFLOW
      - Also accepts DATABASE_URL as a fallback for convenience.
    """

    database_url: Optional[str] = Field(default=None)
    echo: bool = Field(default=False)
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    pool_recycle: Optional[int] = Field(default=None)  # seconds; None -> sensible default
    statement_cache_size: int = Field(default=1000)

    model_config = SettingsConfigDict(
        env_prefix="DB_",        # DB_DATABASE_URL, DB_ECHO, ...
        env_file=".env",
        extra="ignore",
    )

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError(
                "DATABASE_URL or DB_DATABASE_URL must be set for database connectivity"
            )
        # normalize legacy postgres:// to SQLAlchemy async driver url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_db_settings(**kwargs) -> DBSettings:
    # Only include kwargs that are not None, so defaults in DBSettings are used
    filtered = {k: v for k, v in kwargs.items() if v is not None}
    return DBSettings(**filtered)
