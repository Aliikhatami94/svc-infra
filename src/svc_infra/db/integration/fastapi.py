from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Annotated

from fastapi import FastAPI, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine import DBEngine
from ..settings import get_db_settings
from ..uow import UnitOfWork

logger = logging.getLogger(__name__)


def attach_db(app: FastAPI) -> DBEngine:
    settings = get_db_settings()
    engine = DBEngine(settings)

    existing = getattr(app.router, "lifespan_context", None)  # type: ignore[attr-defined]

    @asynccontextmanager
    async def composed_lifespan(_app: FastAPI):
        _app.state.db_engine = engine  # type: ignore[attr-defined]
        try:
            url = engine.engine.url
            try:
                sanitized = url.render_as_string(hide_password=True)  # type: ignore[attr-defined]
            except Exception:
                sanitized = str(url)
            logger.info(
                "DB attached: url=%s driver=%s pool_size=%s max_overflow=%s",
                sanitized,
                getattr(url, "get_backend_name", lambda: "?")(),
                settings.pool_size,
                settings.max_overflow,
            )
            if existing:
                async with existing(_app):  # type: ignore[misc]
                    yield
            else:
                yield
        finally:
            await engine.dispose()

    app.router.lifespan_context = composed_lifespan  # type: ignore[attr-defined]
    return engine


def get_engine(request: Request) -> DBEngine:
    return request.app.state.db_engine  # type: ignore[attr-defined]


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    engine: DBEngine = get_engine(request)
    async with engine.session() as s:
        yield s


async def get_uow(request: Request, read_only: bool = False) -> AsyncIterator[UnitOfWork]:
    engine: DBEngine = get_engine(request)
    async with UnitOfWork(engine, commit_on_success=not read_only) as uow:
        yield uow


EngineDep = Annotated[DBEngine, Depends(get_engine)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UoWDep = Annotated[UnitOfWork, Depends(get_uow)]
