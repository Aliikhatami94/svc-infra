from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from .base import Base
from .engine import DBEngine
from .settings import DBSettings


async def create_all(async_engine: AsyncEngine) -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all(async_engine: AsyncEngine) -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def make_sqlite_memory_engine(*, echo: bool = False) -> DBEngine:
    settings = DBSettings(database_url="sqlite+aiosqlite:///:memory:", echo=echo)
    return DBEngine(settings)

