from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from .engine import DBEngine
from .settings import get_db_settings

logger = logging.getLogger(__name__)


def attach_db(app: FastAPI) -> DBEngine:
    """
    Attach a DBEngine to FastAPI app lifecycle using lifespan, composing with any existing lifespan.
    """
    settings = get_db_settings()
    engine = DBEngine(settings)

    existing = getattr(app.router, "lifespan_context", None)  # type: ignore[attr-defined]

    @asynccontextmanager
    async def composed_lifespan(_app: FastAPI):
        # startup
        _app.state.db_engine = engine  # type: ignore[attr-defined]
        try:
            # Observability: log sanitized DB URL driver and pool
            url = engine.engine.url
            # URL.render_as_string hides password when hide_password=True
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
            # shutdown
            await engine.dispose()

    app.router.lifespan_context = composed_lifespan  # type: ignore[attr-defined]
    return engine
