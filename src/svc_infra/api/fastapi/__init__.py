from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from svc_infra.api.fastapi.dual_router import DualAPIRouter, dualize_router
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.middleware.errors.error_handlers import register_error_handlers
from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.api.fastapi.settings import ApiConfig
from svc_infra.app.env import CURRENT_ENVIRONMENT, LOCAL_ENV
from svc_infra.app.settings import AppSettings, get_app_settings

logger = logging.getLogger(__name__)


def _gen_operation_id_factory():
    used: dict[str, int] = defaultdict(int)

    def _normalize(s: str) -> str:
        return "_".join(x for x in s.strip().replace(" ", "_").split("_") if x)

    def _gen(route: APIRoute) -> str:
        base = route.name or getattr(route.endpoint, "__name__", "op")
        base = _normalize(base)

        tag = _normalize(route.tags[0]) if route.tags else ""
        method = next(iter(route.methods or ["GET"])).lower()

        candidate = base
        if used[candidate]:
            if tag and not base.startswith(tag):
                candidate = f"{tag}_{base}"
            if used[candidate]:
                if not candidate.endswith(f"_{method}"):
                    candidate = f"{candidate}_{method}"
                if used[candidate]:
                    counter = used[candidate] + 1
                    candidate = f"{candidate}_{counter}"

        used[candidate] += 1
        return candidate

    return _gen


def _build_child_api(
    app_config: AppSettings | None,
    api_config: ApiConfig | None,
) -> FastAPI:
    app_settings = get_app_settings(
        name=app_config.name if app_config else None,
        version=app_config.version if app_config else None,
    )

    child = FastAPI(
        title=app_settings.name,
        version=app_settings.version,
        generate_unique_id_function=_gen_operation_id_factory(),
    )

    child.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    child.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(child)

    # NOTE: do NOT register root routers here; this is versioned child only.

    # Optional per-version routers from the app:
    if api_config and api_config.routers_path:
        register_all_routers(
            child,
            base_package=api_config.routers_path,
            prefix="",  # child is mounted at /vX later
            environment=CURRENT_ENVIRONMENT,
        )

    logger.info(
        f"{app_settings.version} version of {app_settings.name} initialized [env: {CURRENT_ENVIRONMENT}]"
    )
    return child


def set_servers(app: FastAPI, public_base_url: str | None, mount_path: str):
    base = mount_path if not public_base_url else f"{public_base_url.rstrip('/')}{mount_path}"

    def custom_openapi():
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema["servers"] = [{"url": base}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


def _setup_cors(app, public_cors_origins: list[str] | str | None = None):
    if isinstance(public_cors_origins, list):
        origins = [o.strip() for o in public_cors_origins if o and o.strip()]
    elif isinstance(public_cors_origins, str):
        origins = [o.strip() for o in public_cors_origins.split(",") if o and o.strip()]
    else:
        fallback = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
        origins = [o.strip() for o in fallback.split(",") if o and o.strip()]

    if not origins:
        return

    cors_kwargs = dict(
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if "*" in origins:
        cors_kwargs["allow_origin_regex"] = ".*"
    else:
        cors_kwargs["allow_origins"] = origins

    app.add_middleware(CORSMiddleware, **cors_kwargs)


def _coerce_list(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [v for v in value if v]


def setup_fastapi(
    versions: list[tuple[AppSettings, ApiConfig]],
    *,
    root_title: str = "Service Shell",
    public_cors_origins: list[str] | str | None = None,
    root_routers_paths: list[str] | str | None = None,
) -> FastAPI:
    """
    - Registers *root* routers (once) on the parent app (e.g. /ping).
    - Mounts each versioned child app at /vX, and registers version routers inside it.
    """
    parent = FastAPI(
        title=root_title,
        docs_url="/docs" if CURRENT_ENVIRONMENT == LOCAL_ENV else None,
        redoc_url="/redoc" if CURRENT_ENVIRONMENT == LOCAL_ENV else None,
        openapi_url="/openapi.json" if CURRENT_ENVIRONMENT == LOCAL_ENV else None,
    )

    _setup_cors(parent, public_cors_origins)

    parent.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(parent)

    # --- 1) Root routers on the parent app ---
    # Always include svc-infra's root health router (adds /ping once at root).
    register_all_routers(
        parent,
        base_package="svc_infra.api.fastapi.routers",
        prefix="",
        environment=CURRENT_ENVIRONMENT,
    )

    # Allow the *app* to also add its own root routers (e.g. your own health/metadata)
    for pkg in _coerce_list(root_routers_paths):
        register_all_routers(
            parent,
            base_package=pkg,
            prefix="",  # root
            environment=CURRENT_ENVIRONMENT,
        )

    # --- 2) Versioned children mounted under /vX ---
    for app_cfg, api_cfg in versions:
        child = _build_child_api(app_cfg, api_cfg)
        mount_path = f"/{api_cfg.version.strip('/')}"  # e.g. "/v0"
        parent.mount(mount_path, child, name=api_cfg.version.strip("/"))
        set_servers(child, api_cfg.public_base_url, mount_path)

    if CURRENT_ENVIRONMENT == LOCAL_ENV:
        from fastapi.responses import HTMLResponse

        @parent.get("/", include_in_schema=False)
        def index():
            links = "".join(
                f'<li><a href="/{api_cfg.version.strip("/")}/docs">/{api_cfg.version.strip("/")}/docs</a></li>'
                for _, api_cfg in versions
            )
            return HTMLResponse(f"<h1>Docs</h1><ul>{links}</ul>")

    return parent


__all__ = [
    "DualAPIRouter",
    "dualize_router",
    "setup_fastapi",
    "ApiConfig",
]
