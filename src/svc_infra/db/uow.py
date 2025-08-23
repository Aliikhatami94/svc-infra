from __future__ import annotations

import asyncio
import inspect
from typing import Type, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from .engine import DBEngine

T = TypeVar("T")


class UnitOfWork:
    def __init__(self, engine: DBEngine, *, commit_on_success: bool = True):
        self._engine = engine
        self._commit_on_success = commit_on_success
        self.session: AsyncSession | None = None
        self._session_cm = None

    async def __aenter__(self) -> "UnitOfWork":
        self._session_cm = self._engine.session()
        self.session = await self._session_cm.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if exc_type is None and self._commit_on_success:
                await self.session.commit()
            else:
                await self.session.rollback()
        finally:
            return await self._session_cm.__aexit__(exc_type, exc, tb)

    def repo(self, model: Type[T]) -> "Repository[T]":
        assert self.session is not None
        # Local import to avoid circular dependency during module import
        from .repository.base import Repository  # type: ignore
        return Repository[T](self.session, model)

    async def begin(self):
        assert self.session is not None
        return await self.session.begin()


def transactional(engine: DBEngine):
    def decorator(fn):
        if inspect.iscoroutinefunction(fn):
            async def aw(*args, **kwargs):
                async with UnitOfWork(engine) as uow:
                    return await fn(*args, uow=uow, **kwargs)
            return aw
        else:
            def sw(*args, **kwargs):
                async def run():
                    async with UnitOfWork(engine) as uow:
                        return fn(*args, uow=uow, **kwargs)
                return asyncio.run(run())
            return sw
    return decorator
