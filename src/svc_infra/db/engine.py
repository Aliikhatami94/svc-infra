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
        engine_kwargs: dict[str, Any] = {
            "echo": settings.echo,
            "future": True,
            "pool_pre_ping": True,
            "pool_recycle": settings.pool_recycle or 1800,
            "pool_timeout": 30,
        }
        if url.startswith("sqlite+aiosqlite://") and ":memory:" in url:
            engine_kwargs["poolclass"] = StaticPool
        else:
            engine_kwargs["pool_size"] = settings.pool_size
            engine_kwargs["max_overflow"] = settings.max_overflow

        if url.startswith("postgresql+asyncpg://"):
            connect_args = engine_kwargs.setdefault("connect_args", {})
            connect_args["statement_cache_size"] = settings.statement_cache_size

        self._engine: AsyncEngine = create_async_engine(url, **engine_kwargs)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine, expire_on_commit=False
        )
        self.cache: BaseCache = cache or NullCache()

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        sess = self._session_factory()
        try:
            yield sess
        finally:
            await sess.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        async with self.session() as sess:
            async with sess.begin():
                yield sess

    async def dispose(self) -> None:
        await self._engine.dispose()
