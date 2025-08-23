from __future__ import annotations
from fastapi import APIRouter, Response, status, Request

from ..health import db_healthcheck

router = APIRouter(tags=["internal"])


@router.get("/_db/health", include_in_schema=False)
async def db_health(request: Request):
    engine = request.app.state.db_engine  # type: ignore[attr-defined]
    async with engine.session() as s:
        ok = await db_healthcheck(s)
    return Response(
        status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    )

