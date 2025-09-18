from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Sequence

from bson import ObjectId
from fastapi import FastAPI

from svc_infra.app.env import CURRENT_ENVIRONMENT, LOCAL_ENV
from svc_infra.db.nosql.management import make_document_crud_schemas
from svc_infra.db.nosql.mongo.client import acquire_db, close_mongo, init_mongo
from svc_infra.db.nosql.mongo.settings import MongoSettings
from svc_infra.db.nosql.repository import NoSqlRepository
from svc_infra.db.nosql.resource import NoSqlResource
from svc_infra.db.nosql.service import NoSqlService
from svc_infra.db.nosql.types import PyObjectId
from svc_infra.db.nosql.utils import get_mongo_dbname_from_env

from .crud_router import make_crud_router_plus_mongo
from .health import make_mongo_health_router


def add_mongo_db_with_url(app: FastAPI, url: str, db_name: str) -> None:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await init_mongo(MongoSettings(url=url, db_name=db_name))
        try:
            expected = get_mongo_dbname_from_env(required=False)
            db = await acquire_db()
            if expected and db.name != expected:
                raise RuntimeError(f"Connected to Mongo DB '{db.name}', expected '{expected}'.")
            yield
        finally:
            await close_mongo()

    app.router.lifespan_context = lifespan


def add_mongo_db(app: FastAPI, *, dsn_env: str = "MONGO_URL") -> None:
    @app.on_event("startup")
    async def _startup() -> None:
        if not os.getenv(dsn_env):
            raise RuntimeError(f"Missing environment variable {dsn_env} for Mongo URL")
        await init_mongo()
        expected = get_mongo_dbname_from_env(required=False)
        db = await acquire_db()
        if expected and db.name != expected:
            raise RuntimeError(f"Connected to Mongo DB '{db.name}', expected '{expected}'.")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await close_mongo()


def add_mongo_health(
    app: FastAPI, *, prefix: str = "/_mongo/health", include_in_schema: bool = False
) -> None:
    if include_in_schema is None:
        include_in_schema = CURRENT_ENVIRONMENT == LOCAL_ENV
    app.include_router(make_mongo_health_router(prefix=prefix, include_in_schema=include_in_schema))


def add_mongo_resources(app: FastAPI, resources: Sequence[NoSqlResource]) -> None:
    for r in resources:
        repo = NoSqlRepository(
            collection_name=r.resolved_collection(),
            id_field=r.id_field,
            soft_delete=r.soft_delete,
            soft_delete_field=r.soft_delete_field,
            soft_delete_flag_field=r.soft_delete_flag_field,
        )
        svc = r.service_factory(repo) if r.service_factory else NoSqlService(repo)

        if r.read_schema and r.create_schema and r.update_schema:
            Read, Create, Update = r.read_schema, r.create_schema, r.update_schema
        elif r.document_model is not None:
            # CRITICAL: teach Pydantic to dump ObjectId/PyObjectId
            Read, Create, Update = make_document_crud_schemas(
                r.document_model,
                create_exclude=r.create_exclude,
                read_name=r.read_name,
                create_name=r.create_name,
                update_name=r.update_name,
                read_exclude=r.read_exclude,
                update_exclude=r.update_exclude,
                json_encoders={ObjectId: str, PyObjectId: str},
            )
        else:
            raise RuntimeError(
                f"Resource for collection '{r.collection}' requires either explicit schemas "
                f"(read/create/update) or a 'document_model' to derive them."
            )

        router = make_crud_router_plus_mongo(
            collection=r.resolved_collection(),
            repo=repo,
            service=svc,
            read_schema=Read,
            create_schema=Create,
            update_schema=Update,
            prefix=r.prefix,
            tags=r.tags,
            search_fields=r.search_fields,
            default_ordering=None,
            allowed_order_fields=None,
        )
        app.include_router(router)
