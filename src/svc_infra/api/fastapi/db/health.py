from __future__ import annotations
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from .integration import SessionDep


def db_health_router(*, prefix: str = "/_db/health", include_in_schema: bool = False) -> APIRouter:
    """Return a simple DB liveness router.

    - prefix: mount path for the health endpoints (default "/_db/health").
    - include_in_schema: whether to show in OpenAPI docs (default False).
    """
    r = APIRouter(prefix=prefix, tags=["health"], include_in_schema=include_in_schema)

    @r.get("", status_code=status.HTTP_200_OK)
    async def db_health(session: SessionDep) -> Response:  # noqa: D401
        # Execute a trivial query to ensure DB/connection pool is alive.
        await session.execute(text("SELECT 1"))
        return Response(status_code=status.HTTP_200_OK)

    return r


__all__ = ["db_health_router"]