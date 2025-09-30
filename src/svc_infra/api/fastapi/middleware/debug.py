import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

log = logging.getLogger("route.debug")


class RouteDebugMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        ep = getattr(route, "endpoint", None) if route else None
        log.info(
            "MATCHED %s %s -> %s", request.method, request.url.path, getattr(ep, "__name__", ep)
        )
        return response
