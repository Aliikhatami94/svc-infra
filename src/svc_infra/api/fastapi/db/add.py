from __future__ import annotations

import os
from typing import Optional, Sequence

from fastapi import FastAPI
from contextlib import asynccontextmanager

from svc_infra.api.fastapi.db.repository import Repository
from svc_infra.api.fastapi.db.service import Service
from svc_infra.api.fastapi.db.crud_router import make_crud_router_plus
from svc_infra.api.fastapi.db.management import make_crud_schemas
from svc_infra.api.fastapi.db.resource import Resource
from .session import _init_engine_and_session
from .health import _make_db_health_router

def add_resources(app: FastAPI, resources: Sequence[Resource]) -> None:
    """
    Mounts CRUD (and extras) for each Resource by creating:
    Repository(model) -> Service(repo) -> router_plus(router with pagination/search/etc.)
    """
    for r in resources:
        # Repository + Service
        repo = Repository(model=r.model, id_attr=r.id_attr, soft_delete=r.soft_delete)
        svc = Service(repo)

        # Schemas: use provided, or autogenerate from the SQLAlchemy model
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

        # Router
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


def add_database(
        app: FastAPI,
        *,
        url: Optional[str] = None,
        dsn_env: str = "DATABASE_URL",
) -> None:
    """
    Configure DB session lifecycle for a FastAPI app.

    - If `url` is provided, uses an app lifespan context (works in all servers).
    - Else, reads from the `dsn_env` environment variable at startup.
    """

    if url:
        # Lifespan path (explicit URL)
        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            global _engine, _SessionLocal
            _engine, _SessionLocal = _init_engine_and_session(url)
            try:
                yield
            finally:
                await _engine.dispose()
                _engine = None
                _SessionLocal = None

        app.router.lifespan_context = lifespan
        return

    # Startup/shutdown hooks path (URL from env)
    @app.on_event("startup")
    async def _startup() -> None:  # noqa: ANN202
        global _engine, _SessionLocal
        if _engine is None:
            env_url = os.getenv(dsn_env)
            if not env_url:
                raise RuntimeError(f"Missing environment variable {dsn_env} for database URL")
            _engine, _SessionLocal = _init_engine_and_session(env_url)

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # noqa: ANN202
        global _engine, _SessionLocal
        if _engine is not None:
            await _engine.dispose()
            _engine = None
            _SessionLocal = None


def add_db_health(
        app: FastAPI,
        *,
        prefix: str = "/_db/health",
        include_in_schema: bool = False,
) -> None:
    """Attach a DB health check endpoint to the FastAPI app."""
    router = _make_db_health_router(prefix=prefix, include_in_schema=include_in_schema)
    app.include_router(router)


__all__ = ["add_resources", "add_database", "add_db_health"]