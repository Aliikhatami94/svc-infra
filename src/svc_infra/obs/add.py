from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Protocol

from svc_infra.obs.settings import ObservabilitySettings


def _want_metrics(cfg: ObservabilitySettings) -> bool:
    return bool(cfg.METRICS_ENABLED)


class RouteClassifier(Protocol):
    def __call__(
        self, route_path: str, method: str
    ) -> str:  # e.g., returns "public|internal|admin"
        ...


def add_observability(
    app: Any | None = None,
    *,
    db_engines: Optional[Iterable[Any]] = None,
    metrics_path: str | None = None,
    skip_metric_paths: Optional[Iterable[str]] = None,
    route_classifier: RouteClassifier | None = None,
) -> Callable[[], None]:
    """
    Enable Prometheus metrics for the ASGI app and optional SQLAlchemy pool metrics.
    Returns a no-op shutdown callable for API compatibility.
    """
    cfg = ObservabilitySettings()

    # --- Metrics (Prometheus) — import lazily so CLIs/tests don’t require prometheus_client
    if app is not None and _want_metrics(cfg):
        try:
            from svc_infra.obs.metrics.asgi import PrometheusMiddleware, add_prometheus  # lazy

            path = metrics_path or cfg.METRICS_PATH
            # If a route_classifier is provided, use a custom route_resolver to append class label
            if route_classifier is None:
                add_prometheus(
                    app,
                    path=path,
                    skip_paths=tuple(skip_metric_paths or (path, "/health", "/healthz")),
                )
            else:
                # Install middleware manually to pass route_resolver
                def _resolver(req):
                    # Base template
                    from svc_infra.obs.metrics.asgi import _route_template  # type: ignore

                    base = _route_template(req)
                    method = getattr(req, "method", "GET")
                    cls = route_classifier(base, method)
                    # Encode as base|class for downstream label splitting in dashboards
                    return f"{base}|{cls}"

                app.add_middleware(
                    PrometheusMiddleware,
                    skip_paths=tuple(skip_metric_paths or (path, "/health", "/healthz")),
                    route_resolver=_resolver,
                )
                # Mount endpoint
                add_prometheus(
                    app,
                    path=path,
                    skip_paths=tuple(skip_metric_paths or (path, "/health", "/healthz")),
                )
        except Exception:
            pass

    # --- DB pool metrics (best effort) — also lazy
    if db_engines:
        try:
            from svc_infra.obs.metrics.sqlalchemy import bind_sqlalchemy_pool_metrics  # lazy

            for eng in db_engines:
                try:
                    bind_sqlalchemy_pool_metrics(eng)
                except Exception:
                    pass
        except Exception:
            pass

    # --- HTTP client metrics (best effort) — import lazily
    try:
        from svc_infra.obs.metrics.http import instrument_httpx, instrument_requests  # lazy

        try:
            instrument_requests()
        except Exception:
            pass
        try:
            instrument_httpx()
        except Exception:
            pass
    except Exception:
        pass

    # Tracing removed; return no-op for backward compatibility
    return lambda: None
