from __future__ import annotations

import logging
import os
from typing import Annotated, AsyncIterator, Tuple

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from svc_infra.db.sql.utils import _coerce_to_async_url

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _init_engine_and_session(
    url: str,
) -> Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    async_url = _coerce_to_async_url(url)
    if async_url != url:
        logger.info(
            "Coerced DB URL driver to async: %s -> %s",
            url.split("://", 1)[0],
            async_url.split("://", 1)[0],
        )
    engine = create_async_engine(async_url)
    session_local = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_local


def initialize_session(url: str) -> None:
    """Create engine + sessionmaker and store them in this module."""
    global _engine, _SessionLocal
    _engine, _SessionLocal = _init_engine_and_session(url)


async def dispose_session() -> None:
    """Dispose engine and clear globals."""
    global _engine, _SessionLocal
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _SessionLocal = None


async def get_session() -> AsyncIterator[AsyncSession]:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call add_sql_db(app, ...) first.")
    async with _SessionLocal() as session:
        # Optional: set a per-transaction statement timeout for Postgres if configured
        raw_ms = os.getenv("DB_STATEMENT_TIMEOUT_MS")
        if raw_ms:
            try:
                ms = int(raw_ms)
                if ms > 0:
                    try:
                        # SET LOCAL applies for the duration of the current transaction only
                        await session.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": ms})
                    except Exception:
                        # Non-PG dialects (e.g., SQLite) will error; ignore silently
                        pass
            except ValueError:
                pass
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SqlSessionDep = Annotated[AsyncSession, Depends(get_session)]

__all__ = ["SqlSessionDep", "initialize_session", "dispose_session"]
