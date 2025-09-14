import logging
import traceback

from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from svc_infra.api.fastapi.middleware.errors.exceptions import FastApiException
from svc_infra.app.env import IS_PROD

logger = logging.getLogger(__name__)


def get_error_type(exc: Exception) -> str:
    return getattr(exc, "error", None) or type(exc).__name__


def log_exception(level: int, exc: Exception, request: Request, status_code: int) -> None:
    logger.log(
        level,
        f"{request.method} {request.url.path} [{status_code}] {type(exc).__name__}: {exc}",
        exc_info=True,
    )


def format_error_response(
    exc: Exception, request: Request, status_code: int, detail: str | dict | list
) -> JSONResponse:
    error_type = get_error_type(exc)
    log_exception(logging.ERROR, exc, request, status_code)

    response_content = {
        "error": error_type,
        "detail": (
            detail
            if not IS_PROD
            else ("Something went wrong. Please contact support." if status_code == 500 else detail)
        ),
    }

    if not IS_PROD and status_code == 500:
        response_content["trace"] = traceback.format_exc()

    return JSONResponse(status_code=status_code, content=response_content)


def register_error_handlers(app):
    @app.exception_handler(FastApiException)
    async def handle_api_frameworks_exception(request: Request, exc: FastApiException):
        return format_error_response(exc, request, exc.status_code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        detail = exc.errors() if not IS_PROD else "Invalid request payload."
        return format_error_response(exc, request, 422, detail)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        return format_error_response(exc, request, exc.status_code, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def handle_starlette_http_exception(request: Request, exc: StarletteHTTPException):
        return format_error_response(exc, request, exc.status_code, exc.detail)

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError):
        return format_error_response(exc, request, 500, "Please try again later.")

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return format_error_response(exc, request, 500, str(exc))

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError):
        msg = str(getattr(exc, "orig", exc))
        if "duplicate key value" in msg or "UniqueViolation" in msg:
            return JSONResponse(status_code=409, content={"detail": "Record already exists."})
        if "not-null" in msg or "NotNullViolation" in msg:
            return JSONResponse(status_code=400, content={"detail": "Missing required field."})
        return JSONResponse(status_code=500, content={"detail": "Database error."})
