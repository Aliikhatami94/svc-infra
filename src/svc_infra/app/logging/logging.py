from __future__ import annotations

import logging
import os
from enum import StrEnum
from typing import Sequence

from pydantic import BaseModel

from svc_infra.app.env import IS_PROD, Environment


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
        import os as _os
        from traceback import format_exception

        payload: dict[str, object] = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "pid": record.process,
            "message": record.getMessage(),
        }

        # Add these two lines:
        if getattr(record, "trace_id", None):
            payload["trace_id"] = record.trace_id
        if getattr(record, "span_id", None):
            payload["span_id"] = record.span_id

        # Optional correlation id
        req_id = getattr(record, "request_id", None)
        if req_id is not None:
            payload["request_id"] = req_id

        # Optional HTTP context
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

        # Optional exception context
        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else None
            exc_message = str(record.exc_info[1]) if record.exc_info[1] else None
            stack = "".join(format_exception(*record.exc_info, chain=True))

            err_obj: dict[str, object] = {}
            if exc_type:
                err_obj["type"] = exc_type
            if exc_message:
                err_obj["message"] = exc_message

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


def _parse_paths_csv(val: str | None) -> list[str]:
    if not val:
        return []
    parts: list[str] = []
    for part in val.replace(",", " ").split():
        p = part.strip()
        if p:
            parts.append(p if p.startswith("/") else f"/{p}")
    return parts


def _env_name_list_to_enum_values(env_names: Sequence[str] | None) -> set[str]:
    """
    Normalize a list like ["prod","test"] into the canonical Environment.value strings.
    Accepts any case and synonyms handled upstream by Environment.
    """
    if not env_names:
        return set()
    normed: set[str] = set()
    # Build a small lookup map {alias -> canonical value}
    alias_map = {
        "local": Environment.LOCAL.value,
        "dev": Environment.DEV.value,
        "development": Environment.DEV.value,
        "test": Environment.TEST.value,
        "preview": Environment.TEST.value,
        "staging": Environment.TEST.value,
        "prod": Environment.PROD.value,
        "production": Environment.PROD.value,
    }
    for name in env_names:
        key = (name or "").strip().lower()
        if not key:
            continue
        if key in (e.value for e in Environment):
            normed.add(key)
        elif key in alias_map:
            normed.add(alias_map[key])
    return normed
