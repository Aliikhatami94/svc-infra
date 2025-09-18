from __future__ import annotations

import logging
import os
from enum import StrEnum
from typing import Sequence, Union

from pydantic import BaseModel

from svc_infra.app.env import (
    DEV_ENV,
    IS_PROD,
    LOCAL_ENV,
    PROD_ENV,
    TEST_ENV,
    Environment,
    get_current_environment,
)
from svc_infra.app.logging.filter import filter_logs_for_paths


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


# --- Enum normalization (accept enums or strings) ---
EnvLike = Union[Environment, str]


def _normalize_env_token(token: EnvLike | None) -> Environment | None:
    if token is None:
        return None
    if isinstance(token, Environment):
        return token
    # string fallback with synonyms handled by Environment via app.env
    key = token.strip().lower()
    alias_map = {
        "local": LOCAL_ENV,
        "dev": DEV_ENV,
        "development": DEV_ENV,
        "test": TEST_ENV,
        "preview": TEST_ENV,
        "staging": TEST_ENV,
        "prod": PROD_ENV,
        "production": PROD_ENV,
    }
    return alias_map.get(key)


def _normalize_env_list(envs: Sequence[EnvLike] | None) -> set[Environment]:
    if not envs:
        return set()
    out: set[Environment] = set()
    for tok in envs:
        norm = _normalize_env_token(tok)
        if norm is not None:
            out.add(norm)
    return out


# --- Main Logging Setup Function ---
def setup_logging(
    level: str | None = None,
    fmt: str | None = None,
    *,
    drop_paths: Sequence[str] | None = None,
    filter_envs: Sequence[EnvLike] | None = (
        PROD_ENV,
        TEST_ENV,
        "prod",
        "production",
        "staging",
        "test",
        "preview",
        "uat",
    ),
) -> None:
    """
    Set up logging for the application.

    Args:
        level: Optional log level (e.g., "DEBUG", "INFO"). If not provided, uses environment-based default.
        fmt: Optional log format ("json" or "plain"). If not provided, uses environment-based default.
        drop_paths: Optional list of URL paths to suppress in access logs (e.g., ["/metrics", "/health"]).
                    If omitted, checks LOG_DROP_PATHS; if still empty and filter is enabled
                    for the current env, defaults to ["/metrics"].
        filter_envs: Environments for which the access-log path filter should be enabled.
                     Accepts Environment enums (preferred) or strings ("prod", "staging", etc.).
                     Default: (PROD_ENV, TEST_ENV).
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

    # Core logging config
    from logging.config import dictConfig

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain": {
                    "format": "%(asctime)s %(levelname)-5s [pid:%(process)d] %(name)s: %(message)s",
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
            "loggers": {
                "uvicorn": {"level": "INFO", "handlers": [], "propagate": True},
                "uvicorn.error": {"level": "INFO", "handlers": [], "propagate": True},
                "uvicorn.access": {"level": "INFO", "handlers": [], "propagate": True},
            },
        }
    )

    # --- Install access-log path filter (after dictConfig) ---
    current_env = get_current_environment()  # Environment
    enabled_envs = _normalize_env_list(filter_envs)
    filter_enabled = current_env in enabled_envs

    # Paths precedence: arg > env > default (if enabled)
    env_paths = _parse_paths_csv(os.getenv("LOG_DROP_PATHS"))
    if drop_paths is not None:
        paths = [p if p.startswith("/") else f"/{p}" for p in drop_paths]
    elif env_paths:
        paths = env_paths
    else:
        paths = ["/metrics"] if filter_enabled else []

    filter_logs_for_paths(paths=paths, enabled=filter_enabled)
