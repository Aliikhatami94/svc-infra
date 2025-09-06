from __future__ import annotations
import os
import logging
from typing import Annotated, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from svc_infra.db.setup.utils import _coerce_to_async_url

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


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
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        global _engine, _SessionLocal
        _engine, _SessionLocal = _init_engine_and_session(url)
        try:
            yield
        finally:
            await _engine.dispose()
            _engine = None
            _SessionLocal = None
    app.router.lifespan_context = lifespan


__all__ = ["SessionDep", "attach_db_to_api", "attach_db_to_api_with_url"]
