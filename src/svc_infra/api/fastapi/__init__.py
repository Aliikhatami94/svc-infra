import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.api.fastapi.middleware.errors.error_handlers import register_error_handlers
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.app.core.settings import get_app_settings
from svc_infra.app import CURRENT_ENVIRONMENT

logger = logging.getLogger(__name__)

def execute_api(
    app_name: str | None = None,
    app_version: str | None = None,
    api_version: str = "/v0",
    routers_path: str | None = None,
    cors_origins: str | None = None,
) -> FastAPI:
    """
    Create and configure a FastAPI application with robust defaults and production best practices.

    Args:
        app_name: Optional app name (overrides default from settings).
        app_version: Optional app version (overrides default from settings).
        api_version: API prefix for all routers (e.g., "/v0").
        routers_path: Optional import path for additional routers.
        cors_origins: Optional comma-separated origins for CORS (defaults to localhost).

    Returns:
        Configured FastAPI app instance.
    """
    app_settings = get_app_settings(name=app_name, version=app_version)
    app = FastAPI(
        title=app_settings.name,
        version=app_settings.version
    )

    # CORS setup
    origins = (cors_origins or os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add catch-all exception middleware before error handlers
    app.add_middleware(CatchAllExceptionMiddleware)

    # Register error handlers globally
    register_error_handlers(app)

    # Register core routers
    try:
        register_all_routers(
            app,
            base_package="svc_infra.api.fastapi.routers",
            prefix=api_version
        )
    except Exception as e:
        logger.error(f"Failed to register core routers: {e}")
        raise

    # Register custom routers if provided
    if routers_path:
        try:
            register_all_routers(
                app,
                base_package=routers_path,
                prefix=api_version,
            )
        except Exception as e:
            logger.error(f"Failed to register custom routers from {routers_path}: {e}")
            raise

    logger.info(f"{app_settings.version} version of {app_settings.name} initialized [env: {CURRENT_ENVIRONMENT}]")

    return app