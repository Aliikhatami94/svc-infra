import logging
import os
from collections import defaultdict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.middleware.errors.error_handlers import register_error_handlers
from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.api.fastapi.settings import ApiConfig
from svc_infra.app.env import CURRENT_ENVIRONMENT
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

        # Prefer the base alone if unique
        candidate = base
        if used[candidate]:
            # Try tag + base if base already taken and tag adds value
            if tag and not base.startswith(tag):
                candidate = f"{tag}_{base}"
            # If still taken, append method
            if used[candidate]:
                # avoid double method suffix if user already named it like ping_get
                if not candidate.endswith(f"_{method}"):
                    candidate = f"{candidate}_{method}"
                # If STILL taken, add a disambiguating counter
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

    # Register core routers (NO global version prefix here)
    register_all_routers(
        child,
        base_package="svc_infra.api.fastapi.routers",
        prefix="",  # <-- key change
    )

    # Optional custom routers
    if api_config and api_config.routers_path:
        register_all_routers(
            child,
            base_package=api_config.routers_path,
            prefix="",  # <-- key change
        )

    logger.info(
        f"{app_settings.version} version of {app_settings.name} initialized [env: {CURRENT_ENVIRONMENT}]"
    )
    return child


def set_servers(app: FastAPI, public_base_url: str | None, mount_path: str):
    # mount_path should be like "/v0" or "/v1"
    base = mount_path if not public_base_url else f"{public_base_url.rstrip('/')}{mount_path}"

    def custom_openapi():
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema["servers"] = [{"url": base}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


def _setup_cors(app, public_cors_origins: list[str] | str | None = None):
    """
    Attach CORS middleware to a FastAPI app.

    - Accepts list or comma-separated str.
    - Falls back to env var CORS_ALLOW_ORIGINS or http://localhost:3000.
    - Handles "*" with allow_credentials=True by switching to regex.
    """
    if isinstance(public_cors_origins, list):
        origins = [o.strip() for o in public_cors_origins if o and o.strip()]
    elif isinstance(public_cors_origins, str):
        origins = [o.strip() for o in public_cors_origins.split(",") if o and o.strip()]
    else:
        fallback = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
        origins = [o.strip() for o in fallback.split(",") if o and o.strip()]

    if not origins:
        return  # nothing to do

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


def create_and_register_api(
    versions: list[tuple[AppSettings, ApiConfig]],
    *,
    public_title: str = "Service Shell",
    public_cors_origins: list[str] | str | None = None,
) -> FastAPI:
    parent = FastAPI(
        title=public_title,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Apply CORS on parent only
    _setup_cors(parent, public_cors_origins)

    parent.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(parent)

    for app_cfg, api_cfg in versions:
        child = _build_child_api(app_cfg, api_cfg)
        mount_path = f"/{api_cfg.version.strip('/')}"  # e.g. "/v0"
        parent.mount(mount_path, child, name=api_cfg.version.strip("/"))
        set_servers(child, api_cfg.public_base_url, mount_path)

    return parent
