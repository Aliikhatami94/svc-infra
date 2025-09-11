from __future__ import annotations

from fastapi import APIRouter

from svc_infra.db.nosql.mongo.client import get_db


async def _ping():
    db = await get_db()
    res = await db.command("ping")
    return {"ok": res.get("ok", 0) == 1}


def make_mongo_health_router(
    *, prefix: str = "/_mongo/health", include_in_schema: bool = False
) -> APIRouter:
    router = APIRouter(prefix=prefix, include_in_schema=include_in_schema)

    @router.get("")
    async def healthcheck():
        return await _ping()

    return router
