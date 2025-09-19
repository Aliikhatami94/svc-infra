from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Iterable, Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

from svc_infra.api.fastapi.docs.landing import CardSpec, DocTargets, render_index_html
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.middleware.errors.error_handlers import register_error_handlers
from svc_infra.api.fastapi.models import APIVersionSpec, ServiceInfo
from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.app.env import CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV

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


def _setup_cors(app: FastAPI, public_cors_origins: list[str] | str | None = None):
    if isinstance(public_cors_origins, list):
        origins = [o.strip() for o in public_cors_origins if o and o.strip()]
    elif isinstance(public_cors_origins, str):
        origins = [o.strip() for o in public_cors_origins.split(",") if o and o.strip()]
    else:
        fallback = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
        origins = [o.strip() for o in fallback.split(",") if o and o.strip()]

    if not origins:
        return

    cors_kwargs = dict(allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
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


def _set_servers(app: FastAPI, public_base_url: str | None, mount_path: str):
    base = mount_path if not public_base_url else f"{public_base_url.rstrip('/')}{mount_path}"

    def custom_openapi():
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema["servers"] = [{"url": base}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


def _build_child_app(service: ServiceInfo, spec: APIVersionSpec) -> FastAPI:
    child = FastAPI(
        title=service.name,
        version=service.release,
        generate_unique_id_function=_gen_operation_id_factory(),
        # let parent control global docs; per-spec override handled via parent index links
    )

    # only parent gets CORS; child shares the same ASGI app after mount
    child.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(child)

    # version routers
    if spec.routers_package:
        register_all_routers(
            child,
            base_package=spec.routers_package,
            prefix="",  # will be mounted under /{tag}
            environment=CURRENT_ENVIRONMENT,
        )

    logger.info(
        "[%s] initialized version %s [env: %s]", service.name, spec.tag, CURRENT_ENVIRONMENT
    )
    return child


def setup_service_api(
    *,
    service: ServiceInfo,
    versions: Sequence[APIVersionSpec],
    root_title: str | None = None,
    root_routers: list[str] | str | None = None,
    public_cors_origins: list[str] | str | None = None,
) -> FastAPI:
    """
    Build the service with:
      - Root app (one set of root routers, incl. svc-infra /ping)
      - One child app per APIVersionSpec mounted at /{tag}
    """
    parent = FastAPI(
        title=root_title or service.name,
        docs_url="/docs" if CURRENT_ENVIRONMENT == LOCAL_ENV else None,
        redoc_url="/redoc" if CURRENT_ENVIRONMENT == LOCAL_ENV else None,
        openapi_url="/openapi.json" if CURRENT_ENVIRONMENT == LOCAL_ENV else None,
        version=service.release,
    )

    _setup_cors(parent, public_cors_origins)

    parent.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(parent)

    # 1) root routers — svc-infra ping at '/', once
    register_all_routers(
        parent,
        base_package="svc_infra.api.fastapi.routers",
        prefix="",
        environment=CURRENT_ENVIRONMENT,
    )
    # app-provided root routers
    for pkg in _coerce_list(root_routers):
        register_all_routers(parent, base_package=pkg, prefix="", environment=CURRENT_ENVIRONMENT)

    # 2) mount each version under /{tag}
    for spec in versions:
        child = _build_child_app(service, spec)
        mount_path = f"/{spec.tag.strip('/')}"
        parent.mount(mount_path, child, name=spec.tag.strip("/"))
        _set_servers(child, spec.public_base_url, mount_path)

    if CURRENT_ENVIRONMENT in (LOCAL_ENV, DEV_ENV):

        @parent.get("/", include_in_schema=False)
        def index():
            cards: list[CardSpec] = []

            # Root card first
            cards.append(
                CardSpec(
                    tag="",  # renders as "/"
                    docs=DocTargets(
                        swagger="/docs",
                        redoc="/redoc",
                        openapi_json="/openapi.json",
                    ),
                )
            )

            # One card per version
            for spec in versions:
                tag = spec.tag.strip("/")
                cards.append(
                    CardSpec(
                        tag=tag,
                        docs=DocTargets(
                            swagger=f"/{tag}/docs",
                            redoc=f"/{tag}/redoc",
                            openapi_json=f"/{tag}/openapi.json",
                        ),
                    )
                )

            html = render_index_html(
                service_name=service.name,
                release=service.release,
                cards=cards,
            )
            return HTMLResponse(html)

    return parent
