from __future__ import annotations

import os
import time
from typing import Any, Callable, Iterable, Optional

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from ..settings import ObservabilitySettings
from .base import counter, gauge, histogram, registry

# ---- Lazy metric creation so that prometheus-client is optional ----

_prom_ready: bool = False
_http_requests_total = None
_http_request_duration = None
_http_inflight = None


def _init_metrics() -> None:
    global _prom_ready, _http_requests_total, _http_request_duration, _http_inflight
    if os.getenv("SVC_INFRA_DISABLE_PROMETHEUS") == "1":
        _prom_ready = False
        return
    if _prom_ready:
        return
    try:
        obs = ObservabilitySettings()
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
        inflight_label = (self.route_resolver or _route_template)(request)
        method = scope.get("method", "GET")
        start = time.perf_counter()

        # If metrics are ready, record inflight
        if _prom_ready and _http_inflight:
            try:
                _http_inflight.labels(inflight_label).inc()
            except Exception:
                pass

        status_code_container: dict[str, Any] = {}

        async def _send(message):
            if message["type"] == "http.response.start":
                status_code_container["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
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
                except Exception:
                    pass
                try:
                    if _http_inflight:
                        _http_inflight.labels(inflight_label).dec()
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
    # Add route
    try:
        from fastapi import APIRouter

        router = APIRouter()
        router.add_api_route(path, endpoint=metrics_endpoint(), include_in_schema=False)
        app.include_router(router)
    except Exception:
        app.add_route(path, metrics_endpoint())
