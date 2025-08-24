from __future__ import annotations
import os
import logging
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _coerce_to_async_url(url: str) -> str:
    """Coerce common sync driver URLs to async-capable URLs.

    - postgresql:// or postgres://        -> postgresql+asyncpg://
    - postgresql+psycopg2:// or +psycopg  -> postgresql+asyncpg://
    - mysql:// or mysql+pymysql://        -> mysql+aiomysql://
    - sqlite://                           -> sqlite+aiosqlite://
    If already async (contains +asyncpg/+aiomysql/+aiosqlite), leave unchanged.
    """
    low = url.lower()
    if "+asyncpg" in low or "+aiomysql" in low or "+aiosqlite" in low:
        return url
    if low.startswith("postgresql+psycopg2://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("postgresql+psycopg://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("mysql+pymysql://") or low.startswith("mysql://"):
        return "mysql+aiomysql://" + url.split("://", 1)[1]
    if low.startswith("sqlite://") and not low.startswith("sqlite+aiosqlite://"):
        return "sqlite+aiosqlite://" + url.split("://", 1)[1]
    return url


def _init_engine_and_session(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    async_url = _coerce_to_async_url(url)
    if async_url != url:
        logger.info("Coerced DB URL driver to async: %s -> %s", url.split("://",1)[0], async_url.split("://",1)[0])
    engine = create_async_engine(async_url)
    session_local = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_local


async def get_session() -> AsyncIterator[AsyncSession]:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call attach_db_to_api(app) first.")
    async with _SessionLocal() as session:
        try:
            yield session
            # if the request handler made changes, this persists them
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def attach_db_to_api(app: FastAPI, *, dsn_env: str = "DATABASE_URL") -> None:
    """Register startup/shutdown hooks to manage an async SQLAlchemy engine.

    Args:
        app: FastAPI application instance.
        dsn_env: Environment variable that contains the async DB URL (sync URLs will be coerced).
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


def attach_db_to_api_with_url(app: FastAPI, *, url: str) -> None:
    """Same as attach_db_to_api but pass URL directly instead of env var (sync URLs will be coerced)."""

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


__all__ = ["SessionDep", "attach_db_to_api", "attach_db_to_api_with_url"]
