import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.api.fastapi.middleware.errors.error_handlers import register_error_handlers
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.settings import ApiConfig
from svc_infra.app.settings import get_app_settings, AppSettings
from svc_infra.app import CURRENT_ENVIRONMENT

logger = logging.getLogger(__name__)

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
    )

    # CORS
    origins = (",".join(api_config.cors_origins) if isinstance(api_config.cors_origins, list)
               else (api_config.cors_origins or os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")))
    origins = [o.strip() for o in origins.split(",")]

    child.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handling
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

    logger.info(f"{app_settings.version} version of {app_settings.name} initialized [env: {CURRENT_ENVIRONMENT}]")
    return child


def create_and_register_api(
        app_config: AppSettings | None = None,
        api_config: ApiConfig | None = None,
) -> FastAPI:
    """
    Creates a parent app and mounts the child API under /{base_prefix}/{version}.
    """
    api_config = api_config or ApiConfig()
    base_prefix = (api_config.base_prefix or "").strip("/")
    version = (api_config.version or "v0").strip("/")

    # Parent app is thin; useful if you later want /healthz, /metrics, multiple versions, etc.
    parent = FastAPI(title="Service Shell")

    # Build child API without any version prefix
    child = _build_child_api(app_config, api_config)

    mount_path = f"/{base_prefix}/{version}" if base_prefix else f"/{version}"
    parent.mount(mount_path, child, name=version)

    # Optional: if behind a reverse proxy that also adds a prefix, set root_path to keep docs/links correct
    # Example: parent = FastAPI(root_path="/gateway")  # or set via uvicorn --root-path /gateway

    return parent