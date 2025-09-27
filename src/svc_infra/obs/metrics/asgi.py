from __future__ import annotations

import os
import time
from typing import Any, Callable, Iterable, Optional

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from ...app.env import CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV
from ..settings import ObservabilitySettings
from .base import counter, gauge, histogram, registry

# ---- Lazy metric creation so that prometheus-client is optional ----

_prom_ready: bool = False
_http_requests_total = None
_http_request_duration = None
_http_inflight = None
_http_response_size = None  # NEW
_http_exceptions_total = None  # NEW
_default_collectors_ready = False  # NEW


def _register_default_collectors_once() -> None:
    """
    Ensure python_info, python_gc_* etc. are available by registering GC collector once.
    Safe to call multiple times.
    """
    global _default_collectors_ready
    if _default_collectors_ready:
        return
    try:
        # These imports are no-ops if already registered by the client,
        # but GCCollector typically needs explicit instantiation.
        from prometheus_client import GCCollector  # type: ignore

        GCCollector()  # registers GC metrics
        _default_collectors_ready = True
    except Exception:
        # If prometheus_client is missing or GCCollector fails, just skip.
        _default_collectors_ready = False


def _init_metrics() -> None:
    global _prom_ready, _http_requests_total, _http_request_duration, _http_inflight
    global _http_response_size, _http_exceptions_total  # NEW
    if os.getenv("SVC_INFRA_DISABLE_PROMETHEUS") == "1":
        _prom_ready = False
        return
    if _prom_ready:
        return
    try:
        obs = ObservabilitySettings()

        # Register default collectors (python_info, python_gc_*).
        _register_default_collectors_once()

        _http_requests_total = counter(
            "http_server_requests_total",
            "Total HTTP requests",
            labels=["method", "route", "code"],
        )
        _http_request_duration = histogram(
            "http_server_request_duration_seconds",
            "HTTP request duration in seconds",
            labels=["route", "method"],
            buckets=obs.METRICS_DEFAULT_BUCKETS,
        )
        _http_inflight = gauge(
            "http_server_inflight_requests",
            "Number of in-flight HTTP requests",
            labels=["route"],
            multiprocess_mode="livesum",
        )
        # NEW: response size histogram (bytes)
        _http_response_size = histogram(
            "http_server_response_size_bytes",
            "HTTP response size in bytes",
            labels=["route", "method"],
            buckets=(256, 512, 1024, 2048, 4096, 8192, 32768, 131072, 524288, 1048576),
        )
        # NEW: exceptions counter
        _http_exceptions_total = counter(
            "http_server_exceptions_total",
            "Unhandled exceptions during request handling",
            labels=["route", "method"],
        )

        _prom_ready = True
    except Exception:
        # prometheus-client not installed (or unavailable) – keep as not ready
        _prom_ready = False


def _route_template(req: Request) -> str:
    route = getattr(req, "scope", {}).get("route")
    if route and hasattr(route, "path_format"):
        return route.path_format
    if route and hasattr(route, "path"):
        return route.path
    return req.url.path or "/*unmatched*"


def _should_skip(path: str, skips: Iterable[str]) -> bool:
    p = path.rstrip("/") or "/"
    return any(p.startswith(s.rstrip("/")) for s in skips)


class PrometheusMiddleware:
    """Minimal, fast metrics middleware for any ASGI app (lazy + optional)."""

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

        # Try to init metrics, but carry on even if we can't
        _init_metrics()

        request = Request(scope, receive=receive)
        route_label = (self.route_resolver or _route_template)(request)
        method = scope.get("method", "GET")
        start = time.perf_counter()

        # If metrics are ready, record inflight
        if _prom_ready and _http_inflight:
            try:
                _http_inflight.labels(route_label).inc()
            except Exception:
                pass

        status_code_container: dict[str, Any] = {}
        bytes_sent = 0  # NEW

        async def _send(message):
            nonlocal bytes_sent
            # capture status code
            if message["type"] == "http.response.start":
                status_code_container["code"] = message["status"]
            # accumulate bytes for response size (handles streaming)
            if message["type"] == "http.response.body":
                body = message.get("body") or b""
                bytes_sent += len(body)
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            # Count exceptions separately (and still observe duration below)
            if _prom_ready and _http_exceptions_total:
                try:
                    _http_exceptions_total.labels(route_label, method).inc()
                except Exception:
                    pass
            # Re-raise so normal error handling applies
            raise
        finally:
            try:
                route_for_stats = _route_template(request)
            except Exception:
                route_for_stats = "/*unknown*"

            elapsed = time.perf_counter() - start
            code = str(status_code_container.get("code", 500))

            if _prom_ready:
                try:
                    if _http_requests_total:
                        _http_requests_total.labels(method, route_for_stats, code).inc()
                    if _http_request_duration:
                        _http_request_duration.labels(route_for_stats, method).observe(elapsed)
                    if _http_response_size:
                        _http_response_size.labels(route_for_stats, method).observe(bytes_sent)
                except Exception:
                    pass
                try:
                    if _http_inflight:
                        _http_inflight.labels(route_label).dec()
                except Exception:
                    pass


def metrics_endpoint():
    """
    Return a Starlette/FastAPI handler that exposes /metrics.
    If prometheus-client is unavailable OR disabled via env, return 501.
    """
    if os.getenv("SVC_INFRA_DISABLE_PROMETHEUS") == "1":

        async def disabled(_):
            return PlainTextResponse(
                "prometheus-client not installed; install svc-infra[metrics] to enable /metrics",
                status_code=501,
            )

        return disabled

    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        # Make sure default collectors are present even if endpoint is hit before any requests
        _register_default_collectors_once()

        reg = registry()

        async def handler(_: Request) -> Response:
            data = generate_latest(reg)
            return Response(content=data, media_type=CONTENT_TYPE_LATEST)

        return handler
    except Exception:

        async def handler(_: Request) -> Response:
            return PlainTextResponse(
                "prometheus-client not installed; install svc-infra[metrics] to enable /metrics",
                status_code=501,
            )

        return handler


def add_prometheus(app, *, path: str = "/metrics", skip_paths: Optional[Iterable[str]] = None):
    """Convenience for FastAPI/Starlette apps."""
    # Add middleware
    app.add_middleware(
        PrometheusMiddleware,
        skip_paths=skip_paths or (path, "/health", "/healthz"),
    )

    try:
        from svc_infra.api.fastapi.dual.public import public_router

        router = public_router()
        router.add_api_route(
            path,
            endpoint=metrics_endpoint(),
            include_in_schema=CURRENT_ENVIRONMENT in (LOCAL_ENV, DEV_ENV),
            tags=["observability"],
        )
        app.include_router(router)
    except Exception:
        app.add_route(path, metrics_endpoint())
