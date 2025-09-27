from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from svc_infra.api.fastapi.dual.public import public_router

from .session import SqlSessionDep


def _make_db_health_router(
    *,
    prefix: str = "/_sql/health",
    include_in_schema: bool = False,
) -> APIRouter:
    """Internal factory for the DB health router."""
    router = public_router(prefix=prefix, tags=["health"], include_in_schema=include_in_schema)

    @router.get("", status_code=status.HTTP_200_OK)
    async def db_health(session: SqlSessionDep) -> Response:
        # Execute a trivial query to ensure DB/connection pool is alive.
        await session.execute(text("SELECT 1"))
        return Response(status_code=status.HTTP_200_OK)

    return router
