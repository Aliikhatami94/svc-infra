from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional, Sequence

from fastapi import FastAPI

from svc_infra.db.sql.management import make_crud_schemas
from svc_infra.db.sql.repository import SqlRepository
from svc_infra.db.sql.resource import SqlResource

from .crud_router import make_crud_router_plus_sql, make_tenant_crud_router_plus_sql
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

        if r.tenant_field:
            # wrap service factory/instance through tenant router
            def _factory():
                return svc

            router = make_tenant_crud_router_plus_sql(
                model=r.model,
                service_factory=_factory,
                read_schema=Read,
                create_schema=Create,
                update_schema=Update,
                prefix=r.prefix,
                tenant_field=r.tenant_field,
                tags=r.tags,
                search_fields=r.search_fields,
                default_ordering=r.ordering_default,
                allowed_order_fields=r.allowed_order_fields,
            )
        else:
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

    # Use lifespan context manager instead of deprecated on_event
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        env_url = os.getenv(dsn_env)
        if not env_url:
            raise RuntimeError(f"Missing environment variable {dsn_env} for database URL")
        initialize_session(env_url)
        try:
            yield
        finally:
            await dispose_session()

    app.router.lifespan_context = lifespan


def add_sql_health(
    app: FastAPI, *, prefix: str = "/_sql/health", include_in_schema: bool = False
) -> None:
    app.include_router(_make_db_health_router(prefix=prefix, include_in_schema=include_in_schema))


def setup_sql(
    app: FastAPI,
    resources: Sequence[SqlResource],
    *,
    url: Optional[str] = None,
    dsn_env: str = "SQL_URL",
    include_health: bool = True,
    health_prefix: str = "/_sql/health",
) -> None:
    """
    Convenience one-liner: configure DB lifecycle, mount CRUD routers, and (optionally) health.

    Internally calls:
      - add_sql_db(app, url=url, dsn_env=dsn_env)
      - add_sql_resources(app, resources)
      - add_sql_health(app, prefix=health_prefix)  [if include_health]

    Idempotent guard: ensures we don't re-run DB init if setup_sql() is called twice.
    """
    # ---- idempotency guard (play nice with tests / multiple imports) ----
    if getattr(app.state, "_sql_setup_done", False):
        # Already wired; you may still add more resources explicitly if needed.
        # But we avoid re-configuring lifecycle & health.
        add_sql_resources(app, resources)
        return

    add_sql_db(app, url=url, dsn_env=dsn_env)
    add_sql_resources(app, resources)

    if include_health:
        add_sql_health(app, prefix=health_prefix, include_in_schema=False)

    app.state._sql_setup_done = True


__all__ = ["add_sql_resources", "add_sql_db", "add_sql_health"]
