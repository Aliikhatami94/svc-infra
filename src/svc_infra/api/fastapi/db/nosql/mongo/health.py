from __future__ import annotations

from fastapi import APIRouter

from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.db.nosql.mongo.client import ping_mongo


def make_mongo_health_router(
    *, prefix: str = "/_mongo/health", include_in_schema: bool = False
) -> APIRouter:
    router = public_router(prefix=prefix, include_in_schema=include_in_schema)

    @router.get("")
    async def healthcheck():
        ok = await ping_mongo()
        return {"ok": ok}

    return router
