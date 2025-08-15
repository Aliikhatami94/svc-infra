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

def create_and_register_api(
    app_config: AppSettings | None = None,
    api_config: ApiConfig | None = None,
) -> FastAPI:
    """
    Build and return a fully configured FastAPI application instance.

    This helper centralizes the common service bootstrap concerns:
      * Loads (or reuses) application settings (name, version, etc.).
      * Applies CORS rules (from ApiConfig.cors_origins or env var CORS_ALLOW_ORIGINS).
      * Installs a catch‑all exception middleware before custom error handlers.
      * Registers global error handlers.
      * Discovers and registers routers (core + optional custom path) honoring the provided API version prefix.

    Args:
        app_config:
            Optional AppSettings instance allowing the caller to override default settings
            (e.g., name, version). If None, internal get_app_settings() will supply defaults.
        api_config:
            Optional ApiConfig instance controlling API surface concerns:
              - version: String prefix applied to all discovered routers (e.g. "/v1").
              - routers_path: Additional import base (module path) to auto‑discover extra routers.
              - cors_origins: Comma separated list of origins for CORS (overrides env var fallback).
            If None, a default ApiConfig (as defined in settings) is assumed by downstream logic.

    Returns:
        A configured FastAPI application ready to be served.

    Logging:
        Emits an info log summarizing initialized app name, version, and active environment.

    Notes:
        * Router discovery uses register_all_routers which will raise on failure (caught and logged here).
        * CatchAllExceptionMiddleware is inserted before specific error handlers to ensure last‑resort capture.
        * CORS origins default to "http://localhost:3000" if neither api_config.cors_origins nor environment var provided.
    """
    app_settings = get_app_settings(
        name=app_config.name,
        version=app_config.version
    )
    app = FastAPI(
        title=app_settings.name,
        version=app_settings.version,
    )

    # CORS setup
    origins = (api_config.cors_origins or os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")).split(",")
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
            prefix=api_config.version
        )
    except Exception as e:
        logger.error(f"Failed to register core routers: {e}")
        raise

    # Register custom routers if provided
    routers_path = api_config.routers_path
    if routers_path:
        try:
            register_all_routers(
                app,
                base_package=routers_path,
                prefix=api_config.version,
            )
        except Exception as e:
            logger.error(f"Failed to register custom routers from {routers_path}: {e}")
            raise

    logger.info(f"{app_settings.version} version of {app_settings.name} initialized [env: {CURRENT_ENVIRONMENT}]")

    return app