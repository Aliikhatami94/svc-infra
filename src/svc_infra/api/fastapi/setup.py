from __future__ import annotations

import logging
import os
from collections import defaultdict
from collections.abc import Iterable, Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from starlette.types import ASGIApp, Receive, Scope, Send

from svc_infra.api.fastapi.docs.landing import CardSpec, DocTargets, render_index_html
from svc_infra.api.fastapi.docs.scoped import DOC_SCOPES
from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers
from svc_infra.api.fastapi.middleware.graceful_shutdown import install_graceful_shutdown
from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware
from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware
from svc_infra.api.fastapi.middleware.request_id import RequestIdMiddleware
from svc_infra.api.fastapi.middleware.timeout import (
    BodyReadTimeoutMiddleware,
    HandlerTimeoutMiddleware,
)
from svc_infra.api.fastapi.openapi.models import APIVersionSpec, ServiceInfo
from svc_infra.api.fastapi.openapi.mutators import setup_mutators
from svc_infra.api.fastapi.openapi.pipeline import apply_mutators
from svc_infra.api.fastapi.routers import register_all_routers
from svc_infra.app.env import CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV

logger = logging.getLogger(__name__)


def _gen_operation_id_factory():
    used: dict[str, int] = defaultdict(int)

    def _normalize(s: str) -> str:
        return "_".join(x for x in s.strip().replace(" ", "_").split("_") if x)

    def _gen(route: APIRoute) -> str:
        base = route.name or getattr(route.endpoint, "__name__", "op")
        base = _normalize(str(base))  # Convert Enum to str if needed
        tag_raw = route.tags[0] if route.tags else ""
        tag = _normalize(str(tag_raw)) if tag_raw else ""
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


def _origin_to_regex(origin: str) -> str | None:
    """Convert a wildcard origin pattern to a regex.

    Supports patterns like:
      - "https://*.vercel.app" -> matches any subdomain
      - "https://nfrax-*.vercel.app" -> matches nfrax-xxx.vercel.app

    Returns None if the origin is not a pattern (no wildcards).
    """
    import re

    if "*" not in origin:
        return None
    # Escape special regex chars except *, then replace * with regex pattern
    escaped = re.escape(origin).replace(r"\*", "[a-zA-Z0-9_-]+")
    return f"^{escaped}$"


def _setup_cors(app: FastAPI, public_cors_origins: list[str] | str | None = None):
    # Collect origins from parameter
    if isinstance(public_cors_origins, list):
        param_origins = [o.strip() for o in public_cors_origins if o and o.strip()]
    elif isinstance(public_cors_origins, str):
        param_origins = [o.strip() for o in public_cors_origins.split(",") if o and o.strip()]
    else:
        param_origins = []

    # Collect origins from environment variable
    env_value = os.getenv("CORS_ALLOW_ORIGINS", "")
    env_origins = [o.strip() for o in env_value.split(",") if o and o.strip()]

    # Merge both sources, removing duplicates while preserving order
    seen = set()
    origins = []
    for o in param_origins + env_origins:
        if o not in seen:
            seen.add(o)
            origins.append(o)

    if not origins:
        return

    cors_kwargs = {"allow_credentials": True, "allow_methods": ["*"], "allow_headers": ["*"]}

    # Check for "*" (allow all) first
    if "*" in origins:
        cors_kwargs["allow_origin_regex"] = ".*"
    else:
        # Separate exact origins from wildcard patterns
        exact_origins = []
        patterns = []
        for o in origins:
            regex = _origin_to_regex(o)
            if regex:
                patterns.append(regex)
            else:
                exact_origins.append(o)

        # If we have patterns, combine into a single regex with exact origins
        if patterns:
            # Convert exact origins to regex patterns too
            import re

            for exact in exact_origins:
                patterns.append(f"^{re.escape(exact)}$")
            # Combine all patterns with OR
            cors_kwargs["allow_origin_regex"] = "|".join(patterns)
        else:
            # No patterns, just use allow_origins
            cors_kwargs["allow_origins"] = exact_origins

    app.add_middleware(CORSMiddleware, **cors_kwargs)  # type: ignore[arg-type]  # CORSMiddleware accepts these kwargs


def _setup_middlewares(app: FastAPI, skip_paths: list[str] | None = None):
    """Configure middleware stack. All middlewares are pure ASGI for streaming compatibility.

    Args:
        app: FastAPI application
        skip_paths: Paths to skip for certain middlewares (e.g., long-running or streaming endpoints)
    """
    paths = skip_paths or []

    app.add_middleware(RequestIdMiddleware)
    # Timeouts: enforce body read timeout first, then total handler timeout
    app.add_middleware(BodyReadTimeoutMiddleware)
    app.add_middleware(HandlerTimeoutMiddleware, skip_paths=paths)
    app.add_middleware(CatchAllExceptionMiddleware)
    # Idempotency and rate limiting
    app.add_middleware(IdempotencyMiddleware, skip_paths=paths)
    app.add_middleware(SimpleRateLimitMiddleware, skip_paths=paths)
    register_error_handlers(app)
    _add_route_logger(app, skip_paths=paths)
    # Graceful shutdown: track in-flight and wait on shutdown
    install_graceful_shutdown(app)


def _coerce_list(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [v for v in value if v]


def _dump_or_none(model):
    return model.model_dump(exclude_none=True) if model is not None else None


def _build_child_app(
    service: ServiceInfo, spec: APIVersionSpec, skip_paths: list[str] | None = None
) -> FastAPI:
    title = f"{service.name} • {spec.tag}" if getattr(spec, "tag", None) else service.name
    child = FastAPI(
        title=title,
        version=service.release,
        contact=_dump_or_none(service.contact),
        license_info=_dump_or_none(service.license),
        terms_of_service=service.terms_of_service,
        description=service.description or "",
        generate_unique_id_function=_gen_operation_id_factory(),
    )

    _setup_middlewares(child, skip_paths=skip_paths)

    # ---- OpenAPI pipeline (DRY!) ----
    include_api_key = bool(spec.include_api_key) if spec.include_api_key is not None else False
    tag_str = str(spec.tag).strip("/")
    mount_path = f"/{tag_str}"
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
            child,
            base_package=spec.routers_package,
            prefix="",
            environment=CURRENT_ENVIRONMENT,
        )

    logger.info(
        "[%s] initialized version %s [env: %s]",
        service.name,
        spec.tag,
        CURRENT_ENVIRONMENT,
    )
    return child


def _build_parent_app(
    service: ServiceInfo,
    *,
    public_cors_origins: list[str] | str | None,
    root_routers: list[str] | str | None,
    root_server_url: str | None = None,
    root_include_api_key: bool = False,
    skip_paths: list[str] | None = None,
    **fastapi_kwargs,  # Accept FastAPI kwargs
) -> FastAPI:
    # Root docs are now enabled in all environments to match root card visibility
    parent = FastAPI(
        title=service.name,
        version=service.release,
        contact=_dump_or_none(service.contact),
        license_info=_dump_or_none(service.license),
        terms_of_service=service.terms_of_service,
        description=service.description or "",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        **fastapi_kwargs,  # Forward to FastAPI constructor
    )

    _setup_cors(parent, public_cors_origins)
    _setup_middlewares(parent, skip_paths=skip_paths)

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


class RouteLoggerMiddleware:
    """Pure ASGI middleware to add X-Handled-By header."""

    def __init__(self, app: ASGIApp, skip_paths: list[str] | None = None):
        self.app = app
        self.skip_paths = skip_paths or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        # Skip specified paths using prefix matching
        if any(path.startswith(skip) for skip in self.skip_paths):
            await self.app(scope, receive, send)
            return

        # Wrap send to add header after response starts
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                route = scope.get("route")
                route_path = getattr(route, "path_format", None) or getattr(route, "path", None)
                if route_path:
                    root_path = scope.get("root_path", "") or ""
                    headers = list(message.get("headers", []))
                    headers.append((b"x-handled-by", f"{method} {root_path}{route_path}".encode()))
                    message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _add_route_logger(app: FastAPI, skip_paths: list[str] | None = None):
    app.add_middleware(RouteLoggerMiddleware, skip_paths=skip_paths)


def setup_service_api(
    *,
    service: ServiceInfo,
    versions: Sequence[APIVersionSpec],
    root_routers: list[str] | str | None = None,
    public_cors_origins: list[str] | str | None = None,
    root_public_base_url: str | None = None,
    root_include_api_key: bool | None = None,
    skip_paths: list[str] | None = None,
    **fastapi_kwargs,  # Forward all other FastAPI kwargs (lifespan, etc.)
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
        skip_paths=skip_paths,
        **fastapi_kwargs,  # Forward to _build_parent_app
    )

    # Mount each version
    for spec in versions:
        child = _build_child_app(service, spec, skip_paths=skip_paths)
        tag_str = str(spec.tag).strip("/")
        mount_path = f"/{tag_str}"
        parent.mount(mount_path, child, name=tag_str)

    @parent.get("/", include_in_schema=False, response_class=HTMLResponse)
    def index():
        cards: list[CardSpec] = []
        is_local_dev = CURRENT_ENVIRONMENT in (LOCAL_ENV, DEV_ENV)

        # Root card - always show in all environments
        cards.append(
            CardSpec(
                tag="",
                docs=DocTargets(swagger="/docs", redoc="/redoc", openapi_json="/openapi.json"),
            )
        )

        # Version cards
        for spec in versions:
            tag = str(spec.tag).strip("/")
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

        if is_local_dev:
            # Scoped cards (auth, payments, etc.)
            for scope, swagger, redoc, openapi_json, title in DOC_SCOPES:
                cards.append(
                    CardSpec(
                        tag=scope.strip("/"),
                        docs=DocTargets(swagger=swagger, redoc=redoc, openapi_json=openapi_json),
                    )
                )

        html = render_index_html(service_name=service.name, release=service.release, cards=cards)
        return HTMLResponse(html)

    return parent
