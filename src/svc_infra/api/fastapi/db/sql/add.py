from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional, Sequence

from fastapi import FastAPI

from svc_infra.db.sql.management import make_crud_schemas
from svc_infra.db.sql.repository import SqlRepository
from svc_infra.db.sql.resource import SqlResource

from .crud_router import make_crud_router_plus_sql
from .health import _make_db_health_router
from .session import dispose_session, initialize_session


def add_sql_resources(app: FastAPI, resources: Sequence[SqlResource]) -> None:
    for r in resources:
        repo = SqlRepository(model=r.model, id_attr=r.id_attr, soft_delete=r.soft_delete)

        if r.service_factory:
            svc = r.service_factory(repo)
        else:
            from svc_infra.db.sql.service import SqlService

            svc = SqlService(repo)

        if r.read_schema and r.create_schema and r.update_schema:
            Read, Create, Update = r.read_schema, r.create_schema, r.update_schema
        else:
            Read, Create, Update = make_crud_schemas(
                r.model,
                create_exclude=r.create_exclude,
                read_name=r.read_name,
                create_name=r.create_name,
                update_name=r.update_name,
            )

        router = make_crud_router_plus_sql(
            model=r.model,
            service=svc,
            read_schema=Read,
            create_schema=Create,
            update_schema=Update,
            prefix=r.prefix,
            tags=r.tags,
            search_fields=r.search_fields,
            default_ordering=r.ordering_default,
            allowed_order_fields=r.allowed_order_fields,
        )
        app.include_router(router)


def add_sql_db(app: FastAPI, *, url: Optional[str] = None, dsn_env: str = "SQL_URL") -> None:
    """Configure DB lifecycle for the app (either explicit URL or from env)."""
    if url:

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            initialize_session(url)
            try:
                yield
            finally:
                await dispose_session()

        app.router.lifespan_context = lifespan
        return

    @app.on_event("startup")
    async def _startup() -> None:  # noqa: ANN202
        env_url = os.getenv(dsn_env)
        if not env_url:
            raise RuntimeError(f"Missing environment variable {dsn_env} for database URL")
        initialize_session(env_url)

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # noqa: ANN202
        await dispose_session()


def add_sql_health(
    app: FastAPI, *, prefix: str = "/_sql/health", include_in_schema: bool = False
) -> None:
    app.include_router(_make_db_health_router(prefix=prefix, include_in_schema=include_in_schema))


__all__ = ["add_sql_resources", "add_sql_db", "add_sql_health"]
