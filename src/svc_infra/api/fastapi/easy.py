from __future__ import annotations

from typing import Iterable, Sequence

from fastapi import FastAPI
from pydantic import BaseModel, Field

from svc_infra.api.fastapi import APIVersionSpec, ServiceInfo, setup_service_api
from svc_infra.app.env import pick
from svc_infra.app.logging import LogLevelOptions, setup_logging
from svc_infra.obs import add_observability

# ---------- Options models ----------


class LoggingOptions(BaseModel):
    enable: bool = Field(default=True, validation_alias="EASY_ENABLE_LOGGING")
    # None -> auto (json in prod, plain elsewhere); level auto if None
    level: str | None = None
    fmt: str | None = None  # "json" | "plain" | None


class ObservabilityOptions(BaseModel):
    enable: bool = Field(default=True, validation_alias="EASY_ENABLE_OBS")
    # Optional extras (only used if enable=True)
    db_engines: Iterable[object] | None = None
    metrics_path: str | None = None  # override /metrics if desired
    skip_metric_paths: Iterable[str] | None = None  # extra skip paths for ASGI metrics


class EasyAppOptions(BaseModel):
    logging: LoggingOptions = LoggingOptions()
    observability: ObservabilityOptions = ObservabilityOptions()


# ---------- Builders ----------


def quick_service_api(
    *,
    name: str,
    release: str,
    versions: Sequence[tuple[str | int, str, str | None]] | None = None,
    root_routers: list[str] | str | None = None,
    public_cors_origins: list[str] | str | None = None,
) -> FastAPI:
    """
    Pure app factory (no logging/obs side-effects).
    """
    service = ServiceInfo(name=name, release=release)
    specs = [
        APIVersionSpec(tag=str(tag), routers_package=pkg, public_base_url=base)
        for (tag, pkg, base) in (versions or [])
    ]
    return setup_service_api(
        service=service,
        versions=specs,
        root_title=name,
        root_routers=root_routers,
        public_cors_origins=public_cors_origins,
    )


def easy_service_app(
    *,
    name: str,
    release: str,
    versions: Sequence[tuple[str | int, str, str | None]] | None = None,
    root_routers: list[str] | str | None = None,
    public_cors_origins: list[str] | str | None = None,
    options: EasyAppOptions | None = None,
    # ---- Back-compat shorthand flags (optional). If provided, they override `options` values. ----
    enable_logging: bool | None = None,
    enable_observability: bool | None = None,
) -> FastAPI:
    """
    One-call bootstrap with a single options object.
    - Logging (env-aware defaults)
    - App wiring (root + versions)
    - Observability (ASGI + optional DB/HTTP metrics)

    Env overrides:
      EASY_ENABLE_LOGGING=true|false
      EASY_ENABLE_OBS=true|false
    """
    opts = (options or EasyAppOptions()).model_copy()

    # Allow shorthand flags to override the model
    if enable_logging is not None:
        opts.logging.enable = bool(enable_logging)
    if enable_observability is not None:
        opts.observability.enable = bool(enable_observability)

    # 1) Logging (if enabled)
    if opts.logging.enable:
        setup_logging(
            level=opts.logging.level
            or pick(
                prod=LogLevelOptions.INFO,
                test=LogLevelOptions.INFO,
                dev=LogLevelOptions.DEBUG,
                local=LogLevelOptions.DEBUG,
            ),
            fmt=opts.logging.fmt,  # None → auto (json in prod, plain elsewhere)
        )

    # 2) App
    app = quick_service_api(
        name=name,
        release=release,
        versions=versions,
        root_routers=root_routers,
        public_cors_origins=public_cors_origins,
    )

    # 3) Observability (if enabled)
    if opts.observability.enable:
        add_observability(
            app,
            db_engines=opts.observability.db_engines,
            metrics_path=opts.observability.metrics_path,
            skip_metric_paths=opts.observability.skip_metric_paths,
        )

    return app
