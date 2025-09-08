from __future__ import annotations

import logging
from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from svc_infra.db.utils import _coerce_to_async_url

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None

def _init_engine_and_session(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
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


async def get_session() -> AsyncIterator[AsyncSession]:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call configure_database(app) first.")
    async with _SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

SessionDep = Annotated[AsyncSession, Depends(get_session)]


__all__ = ["SessionDep","get_session"]