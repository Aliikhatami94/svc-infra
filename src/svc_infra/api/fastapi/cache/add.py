from fastapi import FastAPI

from svc_infra.cache.backend import shutdown_cache
from svc_infra.cache.decorators import init_cache


def setup_caching(app: FastAPI) -> None:
    @app.on_event("startup")
    async def _startup():
        init_cache()

    @app.on_event("shutdown")
    async def _shutdown():
        await shutdown_cache()
