import logging
import traceback
from typing import Any, Dict, Optional

import httpx
from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from svc_infra.api.fastapi.middleware.errors.exceptions import FastApiException
from svc_infra.app.env import IS_PROD

logger = logging.getLogger(__name__)

PROBLEM_MT = "application/problem+json"


def _trace_id_from_request(request: Request) -> Optional[str]:
    # Try common headers first; fall back to None
    for h in ("x-request-id", "x-correlation-id", "x-trace-id"):
        v = request.headers.get(h)
        if v:
            return v
    return None


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    # Convert any non-primitive (e.g., Exception) to string
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def problem_response(
    *,
    status: int,
    title: str,
    detail: str | None = None,
    type_uri: str = "about:blank",
    instance: str | None = None,
    code: str | None = None,
    errors: list[dict] | None = None,
    trace_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    body: Dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status,
    }
    if detail is not None:
        body["detail"] = detail
    if instance is not None:
        body["instance"] = instance
    if code is not None:
        body["code"] = code
    if errors:
        body["errors"] = errors
    if trace_id:
        body["trace_id"] = trace_id
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_MT, headers=headers)


def register_error_handlers(app):
    @app.exception_handler(httpx.TimeoutException)
    async def handle_httpx_timeout(request: Request, exc: httpx.TimeoutException):
        trace_id = _trace_id_from_request(request)
        # Map outbound HTTP client timeouts to 504 Gateway Timeout
        # Keep details generic in prod
        return problem_response(
            status=504,
            title="Gateway Timeout",
            detail=("Upstream request timed out." if IS_PROD else (str(exc) or "httpx timeout")),
            code="GATEWAY_TIMEOUT",
            instance=str(request.url),
            trace_id=trace_id,
        )

    @app.exception_handler(FastApiException)
    async def handle_app_exception(request: Request, exc: FastApiException):
        trace_id = _trace_id_from_request(request)
        title = exc.title or "Bad Request"
        # In prod, keep 500 messages generic
        detail = (
            exc.detail
            if (not IS_PROD or exc.status_code < 500)
            else "Something went wrong. Please contact support."
        )
        return problem_response(
            status=exc.status_code,
            title=title,
            detail=detail,
            code=exc.code,
            instance=str(request.url),
            trace_id=trace_id,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        trace_id = _trace_id_from_request(request)
        raw = exc.errors()
        safe_errors = _json_safe(raw)
        detail = None if IS_PROD else "Validation failed."
        return problem_response(
            status=422,
            title="Unprocessable Entity",
            detail=detail,
            errors=safe_errors if not IS_PROD else None,
            code="VALIDATION_ERROR",
            instance=str(request.url),
            trace_id=trace_id,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        trace_id = _trace_id_from_request(request)
        title = {
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            429: "Too Many Requests",
        }.get(exc.status_code, "Error")
        detail = (
            exc.detail
            if not IS_PROD or exc.status_code < 500
            else "Something went wrong. Please contact support."
        )
        # Preserve headers set on the exception (e.g., Retry-After for rate limits)
        hdrs: dict[str, str] | None = None
        try:
            if getattr(exc, "headers", None):
                # FastAPI/Starlette exceptions store headers as a dict[str, str]
                hdrs = dict(getattr(exc, "headers"))  # type: ignore[arg-type]
        except Exception:
            hdrs = None
        return problem_response(
            status=exc.status_code,
            title=title,
            detail=str(detail) if isinstance(detail, (dict, list)) else detail,
            code=title.replace(" ", "_").upper(),
            instance=str(request.url),
            trace_id=trace_id,
            headers=hdrs,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_starlette_http_exception(request: Request, exc: StarletteHTTPException):
        trace_id = _trace_id_from_request(request)
        title = {
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            429: "Too Many Requests",
        }.get(exc.status_code, "Error")
        detail = (
            exc.detail
            if not IS_PROD or exc.status_code < 500
            else "Something went wrong. Please contact support."
        )
        hdrs: dict[str, str] | None = None
        try:
            if getattr(exc, "headers", None):
                hdrs = dict(getattr(exc, "headers"))  # type: ignore[arg-type]
        except Exception:
            hdrs = None
        return problem_response(
            status=exc.status_code,
            title=title,
            detail=str(detail) if isinstance(detail, (dict, list)) else detail,
            code=title.replace(" ", "_").upper(),
            instance=str(request.url),
            trace_id=trace_id,
            headers=hdrs,
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError):
        trace_id = _trace_id_from_request(request)
        msg = str(getattr(exc, "orig", exc))
        if "duplicate key value" in msg or "UniqueViolation" in msg:
            return problem_response(
                status=409,
                title="Conflict",
                detail="Record already exists.",
                code="CONFLICT",
                instance=str(request.url),
                trace_id=trace_id,
            )
        if "not-null" in msg or "NotNullViolation" in msg:
            return problem_response(
                status=400,
                title="Bad Request",
                detail="Missing required field.",
                code="BAD_REQUEST",
                instance=str(request.url),
                trace_id=trace_id,
            )
        return problem_response(
            status=500,
            title="Internal Server Error",
            detail="Please try again later." if IS_PROD else str(exc),
            code="INTERNAL_ERROR",
            instance=str(request.url),
            trace_id=trace_id,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError):
        trace_id = _trace_id_from_request(request)
        return problem_response(
            status=500,
            title="Internal Server Error",
            detail="Please try again later." if IS_PROD else str(exc),
            code="INTERNAL_ERROR",
            instance=str(request.url),
            trace_id=trace_id,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        trace_id = _trace_id_from_request(request)
        # Log full traceback, but do not leak details in prod
        logger.exception("Unhandled error on %s", request.url.path)
        return problem_response(
            status=500,
            title="Internal Server Error",
            detail=(
                "Something went wrong. Please contact support."
                if IS_PROD
                else "".join(traceback.format_exception(exc))
            ),
            code="INTERNAL_ERROR",
            instance=str(request.url),
            trace_id=trace_id,
        )
