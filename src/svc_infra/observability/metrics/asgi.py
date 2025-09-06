from __future__ import annotations

import time
from typing import Optional, Iterable, Any, Callable
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from ..settings import ObservabilitySettings

# Lazy metric handles (created on first use so prometheus is optional)
_prom_ready = False
_http_requests_total = None
_http_request_duration = None
_http_inflight = None

def _init_metrics() -> None:
    """Create Prometheus metrics only once, on demand."""
    global _prom_ready, _http_requests_total, _http_request_duration, _http_inflight
    if _prom_ready:
        return

    # Import here to keep prometheus optional
    from .base import counter, histogram, gauge  # noqa: WPS433 (intentional lazy import)
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

    # Use livesum so multiprocess collector aggregates properly
    _http_inflight = gauge(
        "http_server_inflight_requests",
        "Number of in-flight HTTP requests",
        labels=["route"],
        multiprocess_mode="livesum",
    )

    _prom_ready = True


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


def _normalize_path_label(path: str) -> str:
    if not path:
        return "/"
    # cheap normalization to avoid empty/duplicate cardinality
    return path.rstrip("/") or "/"


class PrometheusMiddleware:
    """Minimal, fast metrics middleware for any ASGI app with lazy init."""

    def __init__(
            self,
            app: ASGIApp,
            *,
            skip_paths: Optional[Iterable[str]] = None,
            route_resolver: Optional[Callable[[Request], str]] = None,
    ):
        self.app = app
        self.skip_paths = tuple(skip_paths or ("/metrics",))
        self.route_resolver = route_resolver

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or "/"
        if _should_skip(path, self.skip_paths):
            await self.app(scope, receive, send)
            return

        # Initialize metrics on first request (keeps prometheus optional)
        try:
            _init_metrics()
        except Exception:
            # If prometheus is not installed, just pass-through without metrics
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        method = scope.get("method", "GET")
        start = time.perf_counter()

        # Inflight: use the raw path (normalized) so inc/dec match even for 404s
        inflight_label = _normalize_path_label(path)
        _http_inflight.labels(inflight_label).inc()  # type: ignore[attr-defined]

        status_code_container: dict[str, Any] = {}

        async def _send(message):
            if message["type"] == "http.response.start":
                status_code_container["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            # Counters/latency: prefer the route template (lower cardinality)
            try:
                route_for_stats = (
                    (self.route_resolver or _route_template)(request)
                )
            except Exception:
                route_for_stats = "/*unknown*"

            elapsed = time.perf_counter() - start
            code = str(status_code_container.get("code", 500))

            _http_requests_total.labels(method, route_for_stats, code).inc()  # type: ignore[attr-defined]
            _http_request_duration.labels(route_for_stats, method).observe(elapsed)  # type: ignore[attr-defined]
            _http_inflight.labels(inflight_label).dec()  # type: ignore[attr-defined]


def metrics_endpoint():
    """Return a Starlette/FastAPI handler that exposes /metrics."""
    # defer imports so prometheus is optional
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from .base import registry  # noqa: WPS433
    except Exception:
        # If prometheus isn't installed, expose 501 to make it obvious
        async def _oops(_: Request) -> Response:
            return Response("prometheus-client not installed", status_code=501)
        return _oops

    reg = registry()

    async def handler(_: Request) -> Response:
        data = generate_latest(reg)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    return handler


def add_prometheus(app, *, path: str = "/metrics", skip_paths: Optional[Iterable[str]] = None):
    """Convenience for FastAPI/Starlette apps."""
    app.add_middleware(PrometheusMiddleware, skip_paths=skip_paths or (path, "/health", "/healthz"))
    try:
        from fastapi import APIRouter
        router = APIRouter()
        router.add_api_route(path, endpoint=metrics_endpoint(), include_in_schema=False)
        app.include_router(router)
    except Exception:
        app.add_route(path, metrics_endpoint())