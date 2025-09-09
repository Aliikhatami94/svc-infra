from __future__ import annotations
import os
from typing import Optional, Sequence
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .repository import Repository
from .service import Service
from .crud_router import make_crud_router_plus
from .management import make_crud_schemas
from .resource import Resource
from .session import initialize_session, dispose_session
from .health import _make_db_health_router

def add_resources(app: FastAPI, resources: Sequence[Resource]) -> None:
    for r in resources:
        repo = Repository(model=r.model, id_attr=r.id_attr, soft_delete=r.soft_delete)

        # 1) explicit app-provided factory wins
        if r.service_factory:
            svc = r.service_factory(repo)
        # 2) else, generic service
        else:
            svc = Service(repo)

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

        router = make_crud_router_plus(
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

def add_database(app: FastAPI, *, url: Optional[str] = None, dsn_env: str = "DATABASE_URL") -> None:
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

def add_db_health(app: FastAPI, *, prefix: str = "/_db/health", include_in_schema: bool = False) -> None:
    app.include_router(_make_db_health_router(prefix=prefix, include_in_schema=include_in_schema))

__all__ = ["add_resources", "add_database", "add_db_health"]