from __future__ import annotations

import os
from typing import Iterable, Sequence

from fastapi import FastAPI
from pydantic import BaseModel, Field

from svc_infra.api.fastapi.openapi.models import APIVersionSpec, ServiceInfo
from svc_infra.app.env import pick
from svc_infra.app.logging import LogLevelOptions, setup_logging
from svc_infra.obs import add_observability

from .setup import setup_service_api

# ---------- helpers ----------


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str) -> str | None:
    v = os.getenv(name)
    return v.strip() if v and v.strip() else None


def _env_csv_paths(name: str) -> list[str] | None:
    v = os.getenv(name)
    if not v:
        return None
    parts = []
    for p in v.replace(",", " ").split():
        p = p.strip()
        if not p:
            continue
        parts.append(p if p.startswith("/") else f"/{p}")
    return parts


# ---------- Options models ----------


class LoggingOptions(BaseModel):
    enable: bool = Field(default=True)
    # None -> auto (json in prod, plain elsewhere); level auto if None
    level: str | None = None
    fmt: str | None = None  # "json" | "plain" | None


class ObservabilityOptions(BaseModel):
    enable: bool = Field(default=True)
    # Optional extras (only used if enable=True)
    db_engines: Iterable[object] | None = None
    metrics_path: str | None = None
    skip_metric_paths: Iterable[str] | None = None


class EasyAppOptions(BaseModel):
    logging: LoggingOptions = LoggingOptions()
    observability: ObservabilityOptions = ObservabilityOptions()

    @classmethod
    def from_env(cls) -> "EasyAppOptions":
        """
        Build options from environment variables:

          ENABLE_LOGGING=true|false
          ENABLE_OBS=true|false
          LOG_LEVEL=DEBUG|INFO|...
          LOG_FORMAT=json|plain
          METRICS_PATH=/metrics
          OBS_SKIP_PATHS=/metrics,/health,/internal     (csv or space-separated)
        """
        return cls(
            logging=LoggingOptions(
                enable=_env_bool("ENABLE_LOGGING", True),
                level=_env_str("LOG_LEVEL"),
                fmt=_env_str("LOG_FORMAT"),
            ),
            observability=ObservabilityOptions(
                enable=_env_bool("ENABLE_OBS", True),
                metrics_path=_env_str("METRICS_PATH"),
                skip_metric_paths=_env_csv_paths("OBS_SKIP_PATHS"),
            ),
        )

    def merged_with(self, override: "EasyAppOptions | None") -> "EasyAppOptions":
        """
        Merge two option sets. Non-None fields in `override` win.
        (For iterables, if override provides a non-None value, it wins entirely.)
        """
        if override is None:
            return self

        # logging
        log = LoggingOptions(
            enable=(
                override.logging.enable
                if override.logging.enable is not None
                else self.logging.enable
            ),
            level=(
                override.logging.level if override.logging.level is not None else self.logging.level
            ),
            fmt=override.logging.fmt if override.logging.fmt is not None else self.logging.fmt,
        )

        # observability
        obs = ObservabilityOptions(
            enable=(
                override.observability.enable
                if override.observability.enable is not None
                else self.observability.enable
            ),
            db_engines=(
                override.observability.db_engines
                if override.observability.db_engines is not None
                else self.observability.db_engines
            ),
            metrics_path=(
                override.observability.metrics_path
                if override.observability.metrics_path is not None
                else self.observability.metrics_path
            ),
            skip_metric_paths=(
                override.observability.skip_metric_paths
                if override.observability.skip_metric_paths is not None
                else self.observability.skip_metric_paths
            ),
        )

        return EasyAppOptions(logging=log, observability=obs)


# ---------- Builders ----------


def easy_service_api(
    *,
    name: str,
    release: str,
    versions: Sequence[tuple[str | int, str, str | None]] | None = None,
    root_routers: list[str] | str | None = None,
    public_cors_origins: list[str] | str | None = None,
    root_public_base_url: str | None = None,
    root_include_api_key: bool | None = None,
) -> FastAPI:
    service = ServiceInfo(name=name, release=release)
    specs = [
        APIVersionSpec(tag=str(tag), routers_package=pkg, public_base_url=base)
        for (tag, pkg, base) in (versions or [])
    ]
    return setup_service_api(
        service=service,
        versions=specs,
        root_routers=root_routers,
        public_cors_origins=public_cors_origins,
        root_public_base_url=root_public_base_url,
        root_include_api_key=root_include_api_key,
    )


def easy_service_app(
    *,
    name: str,
    release: str,
    versions: Sequence[tuple[str | int, str, str | None]] | None = None,
    root_routers: list[str] | str | None = None,
    public_cors_origins: list[str] | str | None = None,
    root_public_base_url: str | None = None,
    root_include_api_key: bool | None = None,
    options: EasyAppOptions | None = None,
    enable_logging: bool | None = None,
    enable_observability: bool | None = None,
) -> FastAPI:
    """
    One-call bootstrap with env + options + flags:

      Precedence (strongest → weakest):
        1) enable_logging / enable_observability args
        2) `options=` object (per-field)
        3) `EasyAppOptions.from_env()`

      Env recognized:
        ENABLE_LOGGING=true|false
        ENABLE_OBS=true|false
        LOG_LEVEL=DEBUG|INFO|...
        LOG_FORMAT=json|plain
        METRICS_PATH=/metrics
        OBS_SKIP_PATHS=/metrics,/health,/internal
    """
    # 0) Start from env
    env_opts = EasyAppOptions.from_env()
    # 1) Merge explicit options on top
    effective = env_opts.merged_with(options)

    # 2) Apply strongest-prec flags
    if enable_logging is not None:
        effective.logging.enable = bool(enable_logging)
    if enable_observability is not None:
        effective.observability.enable = bool(enable_observability)

    # 3) Logging
    if effective.logging.enable:
        setup_logging(
            level=effective.logging.level
            or pick(
                prod=LogLevelOptions.INFO,
                test=LogLevelOptions.INFO,
                dev=LogLevelOptions.DEBUG,
                local=LogLevelOptions.DEBUG,
            ),
            fmt=effective.logging.fmt,  # None → auto (json in prod, plain elsewhere)
        )

    # 4) App
    app = easy_service_api(
        name=name,
        release=release,
        versions=versions,
        root_routers=root_routers,
        public_cors_origins=public_cors_origins,
        root_public_base_url=root_public_base_url,
        root_include_api_key=root_include_api_key,
    )

    # 5) Observability
    if effective.observability.enable:
        add_observability(
            app,
            db_engines=effective.observability.db_engines,
            metrics_path=effective.observability.metrics_path,
            skip_metric_paths=effective.observability.skip_metric_paths,
        )

    return app
