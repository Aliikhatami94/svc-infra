from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from svc_infra.db.nosql.mongo.session import initialize_mongo, dispose_mongo

def add_mongo(app: FastAPI, *, url: Optional[str] = None, dsn_env: str = "MONGO_URL") -> None:
    if url:
        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            await initialize_mongo(url)
            try:
                yield
            finally:
                await dispose_mongo()
        app.router.lifespan_context = lifespan
        return

    import os
    @app.on_event("startup")
    async def _startup():
        env_url = os.getenv(dsn_env)
        await initialize_mongo(env_url)

    @app.on_event("shutdown")
    async def _shutdown():
        await dispose_mongo()