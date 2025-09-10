from __future__ import annotations

import logging
import os
from enum import StrEnum
from logging.config import dictConfig

from pydantic import BaseModel

from svc_infra.app.env import IS_PROD


# --- Log Format and Level Options ---
class LogFormatOptions(StrEnum):
    PLAIN = "plain"
    JSON = "json"


class LogLevelOptions(StrEnum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"
    NOTSET = "NOTSET"


# --- Pydantic Logging Config Model ---
class LoggingConfig(BaseModel):
    level: LogLevelOptions | None = None
    fmt: LogFormatOptions | None = None


# --- JSON Formatter for Structured Logs ---
class JsonFormatter(logging.Formatter):
    """Structured JSON formatter for prod and CI logs."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        import json
        import os as _os  # avoid shadowing
        from traceback import format_exception

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
            k: v
            for k, v in {
                "method": getattr(record, "http_method", None),
                "path": getattr(record, "path", None),
                "status": getattr(record, "status_code", None),
                "client_ip": getattr(record, "client_ip", None),
                "user_agent": getattr(record, "user_agent", None),
            }.items()
            if v is not None
        }
        if http_ctx:
            payload["http"] = http_ctx

        # Exception context (only when present)
        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else None
            exc_message = str(record.exc_info[1]) if record.exc_info[1] else None
            stack = "".join(format_exception(*record.exc_info, chain=True))

            err_obj: dict[str, object] = {}
            if exc_type:
                err_obj["type"] = exc_type
            if exc_message:
                err_obj["message"] = exc_message

            # Truncate very long stacks to keep lines readable in hosted logs.
            max_stack = int(_os.getenv("LOG_STACK_LIMIT", "4000"))
            err_obj["stack"] = stack[:max_stack] + (
                "...(truncated)" if len(stack) > max_stack else ""
            )

            payload["error"] = err_obj

        return json.dumps(payload, ensure_ascii=False)


# --- Helpers to Read Level/Format ---
def _read_level() -> str:
    explicit = os.getenv("LOG_LEVEL")
    if explicit:
        return explicit.upper()
    from svc_infra.app.env import pick

    return pick(prod="INFO", nonprod="DEBUG", dev="DEBUG", test="DEBUG", local="DEBUG").upper()


def _read_format() -> str:
    fmt = os.getenv("LOG_FORMAT")
    if fmt:
        return fmt.lower()
    return "json" if IS_PROD else "plain"


# --- Main Logging Setup Function ---
def setup_logging(level: str | None = None, fmt: str | None = None) -> None:
    """
    Set up logging for the application.
    Args:
        level: Optional log level (e.g., "DEBUG", "INFO"). If not provided, uses environment-based default.
            You can also use LoggingConfig(level=...) for validation and IDE support.
        fmt: Optional log format ("json" or "plain"). If not provided, uses environment-based default.
            You can also use LoggingConfig(fmt=...) for validation and IDE support.
    """
    # Validate fmt and level using Pydantic if provided
    if fmt is not None or level is not None:
        LoggingConfig(fmt=fmt, level=level)  # raises if invalid
    if level is None:
        level = _read_level()
    if fmt is None:
        fmt = _read_format()

    formatter_name = "json" if fmt == "json" else "plain"

    # Silence multipart parser logs in non-debug environments
    if level.upper() != "DEBUG":
        logging.getLogger("multipart.multipart").setLevel(logging.WARNING)

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
