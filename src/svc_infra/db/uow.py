from __future__ import annotations

from typing import Type, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from .engine import DBEngine
from .repository import Repository

T = TypeVar("T")


class UnitOfWork:
    def __init__(self, engine: DBEngine):
        self._engine = engine
        self.session: AsyncSession | None = None
        self._session_cm = None

    async def __aenter__(self) -> "UnitOfWork":
        self._session_cm = self._engine.session()
        self.session = await self._session_cm.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                await self.session.commit()
            else:
                await self.session.rollback()
        finally:
            # Ensure the session context manager is properly exited
            return await self._session_cm.__aexit__(exc_type, exc, tb)

    def repo(self, model: Type[T]) -> Repository[T]:
        assert self.session is not None
        return Repository[T](self.session, model)


def transactional(engine: DBEngine):
    def decorator(fn):
        async def wrapper(*args, **kwargs):
            async with UnitOfWork(engine) as uow:
                return await fn(*args, uow=uow, **kwargs)
        return wrapper
    return decorator

