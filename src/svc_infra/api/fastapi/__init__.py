import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Sequence
import logging

from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.api.fastapi.middleware.errors.error_handlers import register_error_handlers
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.settings import ApiConfig
from svc_infra.app.settings import get_app_settings, AppSettings
from svc_infra.app import CURRENT_ENVIRONMENT

logger = logging.getLogger(__name__)

def _normalize_origins(origins: str | Sequence[str] | None) -> list[str]:
    if origins is None:
        return ["http://localhost:3000"]
    if isinstance(origins, str):
        return [o.strip() for o in origins.split(",") if o.strip()]
    return list(origins)

def create_and_register_api(
        app_config: AppSettings | None = None,
        api_config: ApiConfig | None = None,
) -> FastAPI:
    # defaults
    app_config = app_config or AppSettings()               # <-- avoid None usage
    api_config = api_config or ApiConfig()

    app_settings = get_app_settings(name=app_config.name, version=app_config.version)

    # IMPORTANT: root_path makes FastAPI generate /v0/* links without changing internal routes
    app = FastAPI(
        title=app_settings.name,
        version=app_settings.version,
        root_path=api_config.version,  # e.g. "/v0"
    )

    origins = _normalize_origins(api_config.cors_origins or os.getenv("CORS_ALLOW_ORIGINS"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(app)

    # NOTE: no version prefix here
    register_all_routers(
        app,
        base_package="svc_infra.api.fastapi.routers",
        prefix="",                           # <-- remove version from routes
    )

    # Optional custom routers
    if api_config.routers_path:
        register_all_routers(
            app,
            base_package=api_config.routers_path,
            prefix="",                       # <-- keep clean
        )

    # Inject OpenAPI "servers" so SDKs see the right base
    def custom_openapi():
        schema = app.openapi_schema or app.openapi()
        schema["servers"] = [{"url": api_config.version}]  # relative base e.g. "/v0"
        return schema
    app.openapi = custom_openapi  # type: ignore[assignment]

    logger.info(f"{app_settings.version} of {app_settings.name} initialized [env: {CURRENT_ENVIRONMENT}]")
    return app