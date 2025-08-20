import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
import logging

from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.api.fastapi.middleware.errors.error_handlers import register_error_handlers
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.settings import ApiConfig
from svc_infra.app.settings import get_app_settings, AppSettings
from svc_infra.app import CURRENT_ENVIRONMENT

logger = logging.getLogger(__name__)

def _gen_operation_id(route: APIRoute) -> str:
    # prefer an explicit route name, then function name
    base = (route.name or getattr(route.endpoint, "__name__", "op")).strip().replace(" ", "_")
    # include tag and method to keep things unique but readable
    tag = (route.tags[0] if route.tags else "").strip().replace(" ", "_")
    method = next(iter(route.methods or ["GET"])).lower()
    parts = [p for p in (tag, base, method) if p]
    return "_".join(parts)

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
        generate_unique_id_function=_gen_operation_id,
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

def set_servers(app, base_url: str | None, version: str):
    # fallback to relative if base_url not provided
    base = (base_url.rstrip("/") + f"/{version}") if base_url else f"/{version}"
    def custom_openapi():
        if app.openapi_schema:
            app.openapi_schema["servers"] = [{"url": base}]
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema["servers"] = [{"url": base}]
        app.openapi_schema = schema
        return schema
    app.openapi = custom_openapi

def create_and_register_api(app_config=None, api_config=None) -> FastAPI:
    api_config = api_config or ApiConfig()

    parent = FastAPI(title="Service Shell")         # thin parent
    child  = _build_child_api(app_config, api_config)  # your existing builder

    mount_path = f"/{api_config.version}"           # e.g., "/v0"
    parent.mount(mount_path, child, name=api_config.version)

    # Make OpenAPI show absolute URL in prod (or relative in dev)
    set_servers(child, api_config.public_base_url, api_config.version)

    # If you’re behind a proxy that already prefixes paths, consider:
    # parent = FastAPI(root_path="/gateway-prefix")  # or uvicorn --root-path ...
    return parent