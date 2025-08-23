from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .engine import DBEngine
from .settings import get_db_settings


def attach_db(app: FastAPI) -> DBEngine:
    """
    Attach a DBEngine to FastAPI app lifecycle using lifespan.

    Usage:
        app = FastAPI()
        db_engine = attach_db(app)
    """
    settings = get_db_settings()
    engine = DBEngine(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # startup
        _app.state.db_engine = engine  # type: ignore[attr-defined]
        try:
            yield
        finally:
            # shutdown
            await engine.dispose()

    # Set/override lifespan context
    app.router.lifespan_context = lifespan  # type: ignore[attr-defined]
    return engine
