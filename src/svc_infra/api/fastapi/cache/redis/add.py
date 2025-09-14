from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from svc_infra.api.fastapi.cache.redis.health import make_cache_health_router
from svc_infra.cache.env import get_cache_url_from_env
from svc_infra.cache.redis.client import close_redis, init_redis


def add_cache_health(
    app: FastAPI, *, prefix: str = "/_cache/health", include_in_schema: bool | None = None
) -> None:
    """
    Add a health endpoint for cache (LOCAL visible by default, hidden elsewhere).
    """
    if include_in_schema is None:
        env = os.getenv("APP_ENV") or os.getenv("ENV") or "local"
        include_in_schema = env.lower() in {"local", "dev", "development"}
    app.include_router(make_cache_health_router(prefix=prefix, include_in_schema=include_in_schema))


def add_cache(app: FastAPI, *, url: Optional[str] = None, dsn_env: str = "REDIS_URL") -> None:
    """
    Configure Redis lifecycle for the app (either explicit URL or from env).
    - Adds `app.state.redis` lazily via acquire_redis() if needed.
    """
    if url:

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            await init_redis(url=url)
            try:
                yield
            finally:
                await close_redis()

        app.router.lifespan_context = lifespan
        return

    @app.on_event("startup")
    async def _startup() -> None:  # noqa: ANN202
        # Will raise with a helpful message if missing
        get_cache_url_from_env(required=True, env_var=dsn_env)
        await init_redis()

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # noqa: ANN202
        await close_redis()


def setup_cache(
    app: FastAPI,
    *,
    url: Optional[str] = None,
    dsn_env: str = "REDIS_URL",
    include_health: bool = True,
    health_prefix: str = "/_cache/health",
) -> None:
    """
    One-liner, idempotent:
      - add_cache()
      - add_cache_health() [optional]
    """
    if getattr(app.state, "_cache_setup_done", False):
        # Already wired; still allow adding health if requested
        if include_health:
            add_cache_health(app, prefix=health_prefix, include_in_schema=None)
        return

    add_cache(app, url=url, dsn_env=dsn_env)
    if include_health:
        add_cache_health(app, prefix=health_prefix, include_in_schema=None)
    app.state._cache_setup_done = True
