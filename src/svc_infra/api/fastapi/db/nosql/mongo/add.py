from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional, Sequence

from fastapi import FastAPI

from svc_infra.db.nosql.mongo.resource import MongoResource
from svc_infra.db.nosql.repository import NoSqlRepository

from .client import close_mongo, init_mongo
from .crud_router import make_mongo_crud_router
from .health import make_mongo_health_router


def add_mongo_database(
    app: FastAPI, *, url: Optional[str] = None, dsn_env: str = "MONGO_URL"
) -> None:
    if url:

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            await init_mongo()
            try:
                yield
            finally:
                await close_mongo()

        app.router.lifespan_context = lifespan
        return

    @app.on_event("startup")
    async def _startup():
        env_url = os.getenv(dsn_env)
        if not env_url:
            raise RuntimeError(f"Missing environment variable {dsn_env} for Mongo URL")
        await init_mongo()

    @app.on_event("shutdown")
    async def _shutdown():
        await close_mongo()


def add_mongo_health(
    app: FastAPI, *, prefix: str = "/_mongo/health", include_in_schema: bool = False
) -> None:
    app.include_router(make_mongo_health_router(prefix=prefix, include_in_schema=include_in_schema))


def add_mongo_resources(app: FastAPI, resources: Sequence[MongoResource]) -> None:
    for r in resources:
        repo = NoSqlRepository(collection_name=r.collection)
        router = make_mongo_crud_router(
            collection=r.collection,
            repo=repo,
            read_schema=r.read_schema,
            create_schema=r.create_schema,
            update_schema=r.update_schema,
            prefix=r.prefix,
            tags=r.tags,
            search_fields=r.search_fields,
        )
        app.include_router(router)
