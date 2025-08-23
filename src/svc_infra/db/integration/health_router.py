from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ..health import db_healthcheck

router = APIRouter(tags=["internal"])


@router.get("/_db/health", include_in_schema=False)
async def db_health(request: Request, verbose: int = 0):
    engine = request.app.state.db_engine  # type: ignore[attr-defined]
    async with engine.session() as s:
        ok = await db_healthcheck(s)
    if not verbose:
        return Response(status_code=200 if ok else 503)
    url = engine.engine.url
    try:
        db_url = url.render_as_string(hide_password=True)  # type: ignore[attr-defined]
    except Exception:
        db_url = str(url)
    info = {
        "ok": ok,
        "driver": getattr(url, "get_backend_name", lambda: "?")(),
        "database": db_url,
    }
    return JSONResponse(status_code=200 if ok else 503, content=info)

