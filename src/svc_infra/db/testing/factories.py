from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from ..base import Base
from ..engine import DBEngine
from ..settings import DBSettings


@asynccontextmanager
async def ephemeral_db() -> AsyncIterator[DBEngine]:
    settings = DBSettings(database_url="sqlite+aiosqlite:///:memory:", echo=False)
    engine = DBEngine(settings)
    async with engine.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()

