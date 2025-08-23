from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from .settings import DBSettings
from .cache import BaseCache, NullCache


class DBEngine:
    """Holds the async SQLAlchemy engine and session factory."""

    def __init__(self, settings: DBSettings, cache: Optional[BaseCache] = None):
        url = settings.resolved_database_url
        # Special handling for SQLite in-memory so multiple sessions share the same DB
        engine_kwargs: dict[str, Any] = {
            "echo": settings.echo,
            "future": True,
        }
        if url.startswith("sqlite+aiosqlite://") and ":memory:" in url:
            engine_kwargs["poolclass"] = StaticPool
        else:
            # Pool args are ignored by some drivers (e.g., SQLite), safe to pass for others
            engine_kwargs["pool_size"] = settings.pool_size
            engine_kwargs["max_overflow"] = settings.max_overflow

        self._engine: AsyncEngine = create_async_engine(url, **engine_kwargs)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine, expire_on_commit=False
        )
        # Pluggable cache; defaults to a no-op implementation
        self.cache: BaseCache = cache or NullCache()

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        sess = self._session_factory()
        try:
            yield sess
        finally:
            await sess.close()

    async def dispose(self) -> None:
        await self._engine.dispose()
