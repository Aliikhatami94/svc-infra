from __future__ import annotations

import logging
import os
from logging.config import dictConfig

from svc_infra.app import IS_PROD, IS_DEV, IS_TEST, IS_LOCAL


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter for prod and CI logs."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        import json
        from traceback import format_exception
        import os as _os  # avoid shadowing

        payload: dict[str, object] = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "pid": record.process,
            "message": record.getMessage(),
        }

        # Correlation id if your middleware adds it
        req_id = getattr(record, "request_id", None)
        if req_id is not None:
            payload["request_id"] = req_id

        # HTTP context (only when present)
        http_ctx = {
            k: v for k, v in {
                "method": getattr(record, "http_method", None),
                "path": getattr(record, "path", None),
                "status": getattr(record, "status_code", None),
                "client_ip": getattr(record, "client_ip", None),
                "user_agent": getattr(record, "user_agent", None),
            }.items() if v is not None
        }
        if http_ctx:
            payload["http"] = http_ctx

        # Exception context (only when present)
        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else None
            exc_message = str(record.exc_info[1]) if record.exc_info[1] else None
            stack = "".join(format_exception(*record.exc_info))

            err_obj: dict[str, object] = {}
            if exc_type:
                err_obj["type"] = exc_type
            if exc_message:
                err_obj["message"] = exc_message

            # Truncate very long stacks to keep lines readable in hosted logs.
            max_stack = int(_os.getenv("LOG_STACK_LIMIT", "4000"))
            err_obj["stack"] = stack[:max_stack] + ("...(truncated)" if len(stack) > max_stack else "")

            payload["error"] = err_obj

        return json.dumps(payload, ensure_ascii=False)


def _read_level() -> str:
    # Allow explicit override first
    explicit = os.getenv("LOG_LEVEL")
    if explicit:
        return explicit.upper()

    # Sensible defaults per environment
    if IS_PROD:
        return "INFO"
    # Local / Dev / Test are more verbose by default
    if IS_LOCAL or IS_DEV or IS_TEST:
        return "DEBUG"

    # Fallback
    return "INFO"


def _read_format() -> str:
    # Prefer env override; otherwise JSON in prod, plain elsewhere
    fmt = os.getenv("LOG_FORMAT")
    if fmt:
        return fmt.lower()
    return "json" if IS_PROD else "plain"


def setup_logging() -> None:
    level = _read_level()
    fmt = _read_format()

    formatter_name = "json" if fmt == "json" else "plain"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,  # keep uvicorn & friends
            "formatters": {
                "plain": {
                    # To include optional HTTP context fields in plain text logs,
                    # use extra={"http_method": ..., "path": ..., "status_code": ...} when logging.
                    "format": "%(asctime)s %(levelname)-5s [pid:%(process)d] %(name)s: %(message)s",
                    # ISO-like; hosting providers often add their own timestamp
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                },
                "json": {
                    "()": JsonFormatter,
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                },
            },
            "handlers": {
                "stream": {
                    "class": "logging.StreamHandler",
                    "level": level,
                    "formatter": formatter_name,
                }
            },
            "root": {
                "level": level,
                "handlers": ["stream"],
            },
            # Let uvicorn loggers bubble up to root handler/format,
            # but keep their level at INFO for sane noise in dev/test.
            "loggers": {
                "uvicorn": {"level": "INFO", "handlers": [], "propagate": True},
                "uvicorn.error": {"level": "INFO", "handlers": [], "propagate": True},
                "uvicorn.access": {"level": "INFO", "handlers": [], "propagate": True},
            },
        }
    )