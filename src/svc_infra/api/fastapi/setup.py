from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Iterable, Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

from svc_infra.api.fastapi.docs.landing import CardSpec, DocTargets, render_index_html
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers
from svc_infra.api.fastapi.openapi.models import APIVersionSpec, ServiceInfo
from svc_infra.api.fastapi.openapi.mutators import setup_mutators
from svc_infra.api.fastapi.openapi.pipeline import apply_mutators
from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.app.env import CURRENT_ENVIRONMENT

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


def _dump_or_none(model):
    return model.model_dump(exclude_none=True) if model is not None else None


def _build_child_app(service: ServiceInfo, spec: APIVersionSpec) -> FastAPI:
    child = FastAPI(
        title=service.name,
        version=service.release,
        contact=_dump_or_none(service.contact),  # FastAPI expects plain dicts
        license_info=_dump_or_none(service.license),
        terms_of_service=service.terms_of_service,
        description=service.description,
        generate_unique_id_function=_gen_operation_id_factory(),
    )

    child.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(child)

    # ---- OpenAPI pipeline (DRY!) ----
    include_api_key = bool(spec.include_api_key) if spec.include_api_key is not None else False
    mount_path = f"/{spec.tag.strip('/')}"
    server_url = (
        mount_path
        if not spec.public_base_url
        else f"{spec.public_base_url.rstrip('/')}{mount_path}"
    )

    mutators = setup_mutators(
        service=service,
        spec=spec,
        include_api_key=include_api_key,
        server_url=server_url,
    )
    apply_mutators(child, *mutators)

    if spec.routers_package:
        register_all_routers(
            child, base_package=spec.routers_package, prefix="", environment=CURRENT_ENVIRONMENT
        )

    logger.info(
        "[%s] initialized version %s [env: %s]", service.name, spec.tag, CURRENT_ENVIRONMENT
    )
    return child


def _build_parent_app(
    service: ServiceInfo,
    *,
    public_cors_origins: list[str] | str | None,
    root_routers: list[str] | str | None,
    root_server_url: str | None = None,
    root_include_api_key: bool = False,  # <-- NEW
) -> FastAPI:
    parent = FastAPI(
        title=service.name,
        version=service.release,
        contact=_dump_or_none(service.contact),
        license_info=_dump_or_none(service.license),
        terms_of_service=service.terms_of_service,
        description=service.description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    _setup_cors(parent, public_cors_origins)
    parent.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(parent)

    mutators = setup_mutators(
        service=service,
        spec=None,
        include_api_key=root_include_api_key,
        server_url=root_server_url,
    )
    apply_mutators(parent, *mutators)

    # Root routers — svc-infra ping at '/', once
    register_all_routers(
        parent,
        base_package="svc_infra.api.fastapi.routers",
        prefix="",
        environment=CURRENT_ENVIRONMENT,
    )
    # app-provided root routers
    for pkg in _coerce_list(root_routers):
        register_all_routers(parent, base_package=pkg, prefix="", environment=CURRENT_ENVIRONMENT)

    return parent


def setup_service_api(
    *,
    service: ServiceInfo,
    versions: Sequence[APIVersionSpec],
    root_routers: list[str] | str | None = None,
    public_cors_origins: list[str] | str | None = None,
    root_public_base_url: str | None = None,
    root_include_api_key: bool | None = None,
) -> FastAPI:
    # infer if not explicitly provided
    effective_root_include_api_key = (
        any(bool(v.include_api_key) for v in versions)
        if root_include_api_key is None
        else bool(root_include_api_key)
    )

    root_server = root_public_base_url.rstrip("/") if root_public_base_url else "/"
    parent = _build_parent_app(
        service,
        public_cors_origins=public_cors_origins,
        root_routers=root_routers,
        root_server_url=root_server,
        root_include_api_key=effective_root_include_api_key,
    )

    # Mount each version
    for spec in versions:
        child = _build_child_app(service, spec)
        mount_path = f"/{spec.tag.strip('/')}"
        parent.mount(mount_path, child, name=spec.tag.strip("/"))

    @parent.get("/", include_in_schema=False)
    def index():
        cards: list[CardSpec] = []

        # Root card first
        cards.append(
            CardSpec(
                tag="",  # renders as "/"
                docs=DocTargets(swagger="/docs", redoc="/redoc", openapi_json="/openapi.json"),
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

        html = render_index_html(service_name=service.name, release=service.release, cards=cards)
        return HTMLResponse(html)

    return parent
