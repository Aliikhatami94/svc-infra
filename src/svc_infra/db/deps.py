from __future__ import annotations

from typing import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from .engine import DBEngine
from .uow import UnitOfWork


def get_engine(request: Request) -> DBEngine:
    return request.app.state.db_engine  # type: ignore[attr-defined]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    engine: DBEngine = get_engine(request)
    async with engine.session() as s:
        yield s


async def get_uow(request: Request) -> AsyncIterator[UnitOfWork]:
    engine: DBEngine = get_engine(request)
    async with UnitOfWork(engine) as uow:
        yield uow
