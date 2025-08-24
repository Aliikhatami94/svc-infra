from __future__ import annotations
import os
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _init_engine_and_session(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url)
    session_local = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_local


async def get_session() -> AsyncIterator[AsyncSession]:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call attach_to_app(app) first.")
    async with _SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def attach_to_app(app: FastAPI, *, dsn_env: str = "DATABASE_URL") -> None:
    """Register startup/shutdown hooks to manage an async SQLAlchemy engine.

    Args:
        app: FastAPI application instance.
        dsn_env: Environment variable that contains the async DB URL.
    """

    @app.on_event("startup")
    async def _startup() -> None:  # noqa: ANN202
        global _engine, _SessionLocal
        if _engine is None:
            url = os.getenv(dsn_env)
            if not url:
                raise RuntimeError(f"Missing environment variable {dsn_env} for database URL")
            _engine, _SessionLocal = _init_engine_and_session(url)

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # noqa: ANN202
        global _engine, _SessionLocal
        if _engine is not None:
            await _engine.dispose()
            _engine = None
            _SessionLocal = None


def attach_to_app_with_url(app: FastAPI, *, url: str) -> None:
    """Same as attach_to_app but pass URL directly instead of env var."""

    @app.on_event("startup")
    async def _startup() -> None:  # noqa: ANN202
        global _engine, _SessionLocal
        if _engine is None:
            _engine, _SessionLocal = _init_engine_and_session(url)

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # noqa: ANN202
        global _engine, _SessionLocal
        if _engine is not None:
            await _engine.dispose()
            _engine = None
            _SessionLocal = None


__all__ = ["SessionDep", "attach_to_app", "attach_to_app_with_url"]

