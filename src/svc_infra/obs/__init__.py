from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from .metrics.asgi import add_prometheus
from .metrics.http import instrument_httpx, instrument_requests
from .metrics.sqlalchemy import bind_sqlalchemy_pool_metrics
from .settings import ObservabilitySettings
from .tracing.setup import setup_tracing


def add_observability(
    app: Any | None = None,
    *,
    service_version: str | None = None,
    deployment_env: str | None = None,
    db_engines: Optional[Iterable[Any]] = None,
    metrics_path: str | None = None,
    skip_metric_paths: Optional[Iterable[str]] = None,
    otlp_headers: Optional[dict[str, str]] = None,
    auto_wire_shutdown: bool = True,
) -> Callable[[], None]:
    """
    Turn on metrics + tracing + client/DB instrumentation in one call.

    - Safe no-ops if optional deps aren't installed.
    - Returns shutdown() you can call on process/app exit to flush spans.
    - If app supports Starlette/FastAPI event hooks, we auto-register shutdown.
    """
    cfg = ObservabilitySettings()

    # --- Metrics (Prometheus)
    if cfg.METRICS_ENABLED and app is not None:
        path = metrics_path or cfg.METRICS_PATH
        add_prometheus(
            app,
            path=path,
            skip_paths=tuple(skip_metric_paths or (path, "/health", "/healthz")),
        )

    # --- DB pool metrics (best effort)
    if db_engines:
        for eng in db_engines:
            try:
                bind_sqlalchemy_pool_metrics(eng)
            except Exception:
                pass

    # --- Tracing (OpenTelemetry)
    shutdown_tracing: Callable[[], None] = lambda: None
    if cfg.OTEL_ENABLED:
        shutdown_tracing = setup_tracing(
            service_name=cfg.OTEL_SERVICE_NAME,
            endpoint=cfg.OTEL_EXPORTER_OTLP_ENDPOINT,
            protocol=cfg.OTEL_EXPORTER_PROTOCOL,
            sample_ratio=cfg.OTEL_SAMPLER_RATIO,
            service_version=service_version,
            deployment_env=deployment_env,
            headers=otlp_headers,
            instrument_fastapi=True,
            instrument_sqlalchemy=True,
            instrument_requests=True,
            instrument_httpx=True,
        )

    # --- HTTP client metrics (best effort)
    try:
        instrument_requests()
    except Exception:
        pass
    try:
        instrument_httpx()
    except Exception:
        pass

    # --- Auto-wire shutdown to app if possible
    if auto_wire_shutdown and app is not None:
        try:
            if hasattr(app, "add_event_handler"):
                app.add_event_handler("shutdown", shutdown_tracing)
            elif hasattr(app, "on_event"):
                app.on_event("shutdown")(shutdown_tracing)  # type: ignore[misc]
        except Exception:
            pass

    return shutdown_tracing
