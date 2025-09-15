from __future__ import annotations

from fastapi import Response, status

from svc_infra.api.fastapi import DualAPIRouter
from svc_infra.cache.redis.client import acquire_redis


def make_cache_health_router(
    *, prefix: str = "/_cache/health", include_in_schema: bool = False
) -> DualAPIRouter:
    router = DualAPIRouter(prefix=prefix, tags=["health"], include_in_schema=include_in_schema)

    @router.get("", status_code=status.HTTP_200_OK)
    async def cache_health() -> Response:
        client = await acquire_redis()
        # 'PING' returns b'PONG' with redis-py asyncio
        pong = await client.ping()
        return Response(
            status_code=status.HTTP_200_OK if pong else status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return router
