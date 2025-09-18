from __future__ import annotations

from typing import Iterable, Sequence

from fastapi import FastAPI

from svc_infra.api.fastapi import APIVersionSpec, ServiceInfo, setup_service_api
from svc_infra.app.env import pick
from svc_infra.app.logging import LogLevelOptions, setup_logging
from svc_infra.obs import add_observability


def quick_service_api(
    *,
    name: str,
    release: str,
    versions: Sequence[tuple[str | int, str, str | None]] | None = None,
    root_routers: list[str] | str | None = None,
    public_cors_origins: list[str] | str | None = None,
) -> "FastAPI":
    """
    The smallest useful builder:
      quick_app(name="My API", release="0.1.0",
                versions=[("v0", "myapi.routers.v0", "http://0.0.0.0:8000")],
                root_routers="myapi.routers.root")

    - Attaches svc-infra /ping to root once
    - Adds your root routers (if any) at "/"
    - Mounts each version under "/{tag}"
    - No logging or observability side-effects (pure app factory)
    """
    service = ServiceInfo(name=name, release=release)
    specs = [
        APIVersionSpec(tag=tag, routers_package=pkg, public_base_url=base)
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
    # Optional niceties:
    log_level: str | None = None,
    log_format: str | None = None,  # "json" | "plain" | None (auto)
    db_engines: Iterable[object] | None = None,  # to enable DB pool metrics
) -> "FastAPI":
    """
    One-call bootstrap:
      - Sensible logging defaults (env-aware)
      - App wiring (root + versions)
      - Observability (ASGI + optional DB/HTTP client metrics)

    Example:
        app = easy_app(
            name="APIFrameworks API",
            release="0.1.0",
            root_routers="apiframeworks_api.routers.root",
            versions=[("v0", "apiframeworks_api.routers.v0", "http://0.0.0.0:8000")],
        )
    """
    # 1) Logging
    setup_logging(
        level=log_level
        or pick(
            prod=LogLevelOptions.INFO,
            test=LogLevelOptions.INFO,
            dev=LogLevelOptions.DEBUG,
            local=LogLevelOptions.DEBUG,
        ),
        fmt=log_format,  # None → auto (json in prod, plain elsewhere)
    )

    # 2) App
    app = quick_service_api(
        name=name,
        release=release,
        versions=versions,
        root_routers=root_routers,
        public_cors_origins=public_cors_origins,
    )

    # 3) Observability (ASGI + HTTP client; DB optional)
    add_observability(app, db_engines=db_engines)

    return app
