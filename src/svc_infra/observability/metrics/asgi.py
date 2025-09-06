from __future__ import annotations

import time
from typing import Optional, Iterable, Any, Callable
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .base import registry, counter, histogram, gauge
from ..settings import ObservabilitySettings

# Default buckets come from settings at import time (safe for gunicorn workers)
_obs = ObservabilitySettings()

_http_requests_total = counter(
    "http_server_requests_total",
    "Total HTTP requests",
    labels=["method", "route", "code"],
)

_http_request_duration = histogram(
    "http_server_request_duration_seconds",
    "HTTP request duration in seconds",
    labels=["route", "method"],
    buckets=_obs.METRICS_DEFAULT_BUCKETS,
)

_http_inflight = gauge(
    "http_server_inflight_requests",
    "Number of in-flight HTTP requests",
    labels=["route"],
    multiprocess_mode="livesum",
)

def _route_template(req: Request) -> str:
    # FastAPI/Starlette exposes route.path_format (or route.path) AFTER routing
    route = getattr(req, "scope", {}).get("route")
    if route and hasattr(route, "path_format"):
        return route.path_format
    if route and hasattr(route, "path"):
        return route.path
    # Fallback when not resolved (e.g., 404)
    return "/*unmatched*"

def _should_skip(path: str, skips: Iterable[str]) -> bool:
    p = path.rstrip("/") or "/"
    return any(p.startswith(s.rstrip("/")) for s in skips)

class PrometheusMiddleware:
    """Minimal, fast metrics middleware for any ASGI app."""

    def __init__(
            self,
             app: ASGIApp, *,
             skip_paths: Optional[Iterable[str]] = None,
             route_resolver: Optional[Callable[[Request], str]] = None
         ):
        self.app = app
        self.skip_paths = tuple(skip_paths or ("/metrics",))
        self.route_resolver = route_resolver

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast short-circuit on skip
        path = scope.get("path") or "/"
        if _should_skip(path, self.skip_paths):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        route = (self.route_resolver or _route_template)(request)
        method = scope.get("method", "GET")
        start = time.perf_counter()

        # track in-flight (route is unknown until after route resolution; use placeholder)
        _http_inflight.labels(route).inc()

        status_code_container: dict[str, Any] = {}

        async def _send(message):
            if message["type"] == "http.response.start":
                status_code_container["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            # Recompute route after endpoint resolved
            try:
                route = _route_template(request)
            except Exception:
                route = "/*unknown*"

            elapsed = time.perf_counter() - start
            code = str(status_code_container.get("code", 500))

            _http_requests_total.labels(method, route, code).inc()
            _http_request_duration.labels(route, method).observe(elapsed)
            _http_inflight.labels(route).inc(-1)

def metrics_endpoint():
    """Return a Starlette/FastAPI handler that exposes /metrics."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    reg = registry()

    async def handler(_: Request) -> Response:
        data = generate_latest(reg)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    return handler

def add_prometheus(app, *, path: str = "/metrics", skip_paths: Optional[Iterable[str]] = None):
    """Convenience for FastAPI/Starlette apps."""
    # Add middleware
    app.add_middleware(PrometheusMiddleware, skip_paths=skip_paths or (path, "/health", "/healthz"))
    # Add route
    try:
        from fastapi import APIRouter
        router = APIRouter()
        router.add_api_route(path, endpoint=metrics_endpoint(), include_in_schema=False)
        app.include_router(router)
    except Exception:
        # Fall back for pure Starlette
        app.add_route(path, metrics_endpoint())