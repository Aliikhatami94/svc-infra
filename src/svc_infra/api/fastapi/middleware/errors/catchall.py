from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class CatchAllExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error(f"{type(exc).__name__} on {request.url.path} (500): {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": type(exc).__name__,
                    "detail": str(exc)
                }
            )