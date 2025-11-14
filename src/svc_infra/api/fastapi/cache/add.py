from contextlib import asynccontextmanager

from fastapi import FastAPI

from svc_infra.cache.backend import shutdown_cache
from svc_infra.cache.decorators import init_cache


def setup_caching(app: FastAPI) -> None:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_cache()
        try:
            yield
        finally:
            await shutdown_cache()

    app.router.lifespan_context = lifespan
