from __future__ import annotations

import logging
import os
from logging.config import dictConfig
from typing import Sequence

from svc_infra.app.env import CURRENT_ENVIRONMENT

from .filter import filter_logs_for_paths
from .formats import (
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
    """Configure logging + optional access-log path filtering."""
    if fmt is not None or level is not None:
        LoggingConfig(fmt=fmt, level=level)  # pydantic validation

    if level is None:
        level = _read_level()
    if fmt is None:
        fmt = _read_format()

    formatter_name = "json" if fmt == "json" else "plain"

    # Silence chattier libs outside DEBUG
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
            "root": {"level": level, "handlers": ["stream"]},
            "loggers": {
                "uvicorn": {"level": "INFO", "handlers": [], "propagate": True},
                "uvicorn.error": {"level": "INFO", "handlers": [], "propagate": True},
                "uvicorn.access": {"level": "INFO", "handlers": [], "propagate": True},
            },
        }
    )

    # Access-log path filter
    enabled_envs = _env_name_list_to_enum_values(filter_envs)
    filter_enabled = CURRENT_ENVIRONMENT.value in enabled_envs

    env_paths = _parse_paths_csv(os.getenv("LOG_DROP_PATHS"))
    if drop_paths is not None:
        paths = list(drop_paths)
    elif env_paths:
        paths = env_paths
    else:
        paths = ["/metrics"] if filter_enabled else []

    filter_logs_for_paths(paths=paths, enabled=filter_enabled)
