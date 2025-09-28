from __future__ import annotations

import logging
import traceback
import uuid
from typing import Any

from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from svc_infra.api.fastapi.middleware.errors.exceptions import FastApiException
from svc_infra.app.env import IS_PROD

logger = logging.getLogger(__name__)


def _problem(
    *,
    status: int,
    title: str,
    detail: str | dict | list | None = None,
    type_uri: str | None = None,
    instance: str | None = None,
    code: str | None = None,
    errors: list[dict] | None = None,
    trace: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": status,
        "title": title,
    }
    if type_uri:
        body["type"] = type_uri
    if instance:
        body["instance"] = instance
    if detail is not None:
        body["detail"] = detail
    if code:
        body["code"] = code
    if errors:
        body["errors"] = errors
    if not IS_PROD and trace:
        body["trace"] = trace
    return body


def register_error_handlers(app):
    def _instance_path(request: Request) -> str:
        # stable per-request id could be injected via middleware (trace id)
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        return f"urn:request:{rid}"

    @app.exception_handler(FastApiException)
    async def handle_framework_exc(request: Request, exc: FastApiException):
        trace = traceback.format_exc() if not IS_PROD and exc.status_code >= 500 else None
        body = _problem(
            status=exc.status_code,
            title=exc.error or "Bad Request",
            detail=exc.detail,
            code=exc.error,
            instance=_instance_path(request),
            trace=trace,
        )
        return JSONResponse(
            status_code=exc.status_code, content=body, media_type="application/problem+json"
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        body = _problem(
            status=422,
            title="Unprocessable Entity",
            detail=("Invalid request payload." if IS_PROD else "Validation failed."),
            errors=(None if IS_PROD else errors),
            code="validation_error",
            instance=_instance_path(request),
        )
        return JSONResponse(status_code=422, content=body, media_type="application/problem+json")

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        body = _problem(
            status=exc.status_code,
            title=getattr(exc, "detail", None) or "HTTP Error",
            detail=None if IS_PROD and exc.status_code >= 500 else getattr(exc, "detail", None),
            code=getattr(exc, "detail", None) if isinstance(exc.detail, str) else None,
            instance=_instance_path(request),
        )
        return JSONResponse(
            status_code=exc.status_code, content=body, media_type="application/problem+json"
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_starlette_http_exception(request: Request, exc: StarletteHTTPException):
        body = _problem(
            status=exc.status_code,
            title=str(exc.detail) if exc.detail else "HTTP Error",
            detail=None if IS_PROD and exc.status_code >= 500 else str(exc.detail),
            code=str(exc.detail) if isinstance(exc.detail, str) else None,
            instance=_instance_path(request),
        )
        return JSONResponse(
            status_code=exc.status_code, content=body, media_type="application/problem+json"
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError):
        msg = str(getattr(exc, "orig", exc))
        if "duplicate key value" in msg or "UniqueViolation" in msg:
            body = _problem(
                status=409,
                title="Conflict",
                detail="Record already exists.",
                code="conflict",
                instance=_instance_path(request),
            )
            return JSONResponse(
                status_code=409, content=body, media_type="application/problem+json"
            )
        if "not-null" in msg or "NotNullViolation" in msg:
            body = _problem(
                status=400,
                title="Bad Request",
                detail="Missing required field.",
                code="bad_request",
                instance=_instance_path(request),
            )
            return JSONResponse(
                status_code=400, content=body, media_type="application/problem+json"
            )
        body = _problem(
            status=500,
            title="Database Error",
            detail=("Please try again later." if IS_PROD else msg),
            code="db_error",
            instance=_instance_path(request),
        )
        return JSONResponse(status_code=500, content=body, media_type="application/problem+json")

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError):
        body = _problem(
            status=500,
            title="Database Error",
            detail="Please try again later.",
            code="db_error",
            instance=_instance_path(request),
        )
        return JSONResponse(status_code=500, content=body, media_type="application/problem+json")

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s", request.url.path)
        body = _problem(
            status=500,
            title="Internal Server Error",
            detail=("Something went wrong. Please contact support." if IS_PROD else str(exc)),
            code="internal_error",
            instance=_instance_path(request),
            trace=(None if IS_PROD else traceback.format_exc()),
        )
        return JSONResponse(status_code=500, content=body, media_type="application/problem+json")
