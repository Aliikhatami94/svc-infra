import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.api.fastapi.middleware.errors.error_handlers import register_error_handlers
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.app.core.settings import get_app_settings
from svc_infra.app import ENV

logger = logging.getLogger(__name__)

def execute_api(
        name = None,
        app_version = None,
        api_version = "/v0",
        routers_path = None,
        routers_exclude: dict = None
) -> FastAPI:
    app_settings = get_app_settings(name=name, version=app_version)
    app = FastAPI(
        title=app_settings.name,
        version=app_settings.version
    )

    # Set CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add catch-all exception middleware before error handlers
    app.add_middleware(CatchAllExceptionMiddleware)

    # Register error handlers globally
    register_error_handlers(app)

    # svc_infra routers
    register_all_routers(
        app,
        base_package="svc_infra.api.fastapi.routers",
        prefix=api_version
    )

    # Custom routers if provided
    if routers_path:
        register_all_routers(
            app,
            base_package=routers_path,
            prefix=api_version,
            exclude=routers_exclude
        )

    logger.info(f"{name} initialized [env: {ENV}]")

    return app