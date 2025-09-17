import logging
import os
from logging.config import dictConfig
from typing import Sequence

from svc_infra.app.env import get_current_environment
from svc_infra.app.logging.filter import filter_logs_for_paths

from .logging import (
    JsonFormatter,
    LoggingConfig,
    _env_name_list_to_enum_values,
    _parse_paths_csv,
    _read_format,
    _read_level,
)


def setup_logging(
    level: str | None = None,
    fmt: str | None = None,
    *,
    drop_paths: Sequence[str] | None = None,
    filter_envs: Sequence[str] | None = ("prod", "test"),
) -> None:
    """
    Set up logging for the application.

    Args:
        level: Optional log level (e.g., "DEBUG", "INFO"). If not provided, uses environment-based default.
        fmt: Optional log format ("json" or "plain"). If not provided, uses environment-based default.
        drop_paths: Optional list of URL paths to suppress in access logs (e.g., ["/metrics", "/health"]).
                    If omitted, checks LOG_FILTER_DROP_PATHS; if still empty and filter is enabled
                    for the current env, defaults to ["/metrics"].
        filter_envs: Environments for which the access-log path filter should be enabled.
                    Accepts names like "prod", "production", "test", "staging", "dev", "local".
                    Default: ("prod", "test").
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
    current_env = get_current_environment().value  # "local" | "dev" | "test" | "prod"
    enabled_envs = _env_name_list_to_enum_values(filter_envs)
    filter_enabled = current_env in enabled_envs

    # Paths precedence: arg > env > default (if enabled)
    env_paths = _parse_paths_csv(os.getenv("LOG_DROP_PATHS"))
    if drop_paths is not None:
        paths = list(drop_paths)
    elif env_paths:
        paths = env_paths
    else:
        paths = ["/metrics"] if filter_enabled else []

    filter_logs_for_paths(paths=paths, enabled=filter_enabled)
