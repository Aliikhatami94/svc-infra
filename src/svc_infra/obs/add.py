from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from svc_infra.obs.settings import ObservabilitySettings
from svc_infra.obs.tracing.setup import setup_tracing


def _want_metrics(cfg: ObservabilitySettings) -> bool:
    mode = (cfg.OBS_MODE or "both").lower()
    return cfg.OTEL_ENABLED and mode in {"both", "uptrace"}


def _want_tracing(cfg: ObservabilitySettings) -> bool:
    mode = (cfg.OBS_MODE or "both").lower()
    return cfg.OTEL_ENABLED and mode in {"both", "uptrace"}


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
    cfg = ObservabilitySettings()

    # --- Metrics (Prometheus) — import lazily so MCP/CLI doesn’t require prometheus_client
    if app is not None and _want_metrics(cfg):
        try:
            from svc_infra.obs.metrics.asgi import add_prometheus  # lazy

            path = metrics_path or cfg.METRICS_PATH
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

    # --- Tracing (OpenTelemetry)
    shutdown_tracing: Callable[[], None] = lambda: None
    if _want_tracing(cfg):
        headers = dict(otlp_headers or {})
        if getattr(cfg, "UPTRACE_DSN", None) and "uptrace-dsn" not in {
            k.lower(): v for k, v in headers.items()
        }:
            headers["uptrace-dsn"] = cfg.UPTRACE_DSN

        shutdown_tracing = setup_tracing(
            service_name=cfg.OTEL_SERVICE_NAME,
            endpoint=cfg.OTEL_EXPORTER_OTLP_ENDPOINT,
            protocol=cfg.OTEL_EXPORTER_PROTOCOL,
            sample_ratio=cfg.OTEL_SAMPLER_RATIO,
            service_version=service_version,
            deployment_env=deployment_env,
            headers=headers or None,
            instrument_fastapi=True,
            instrument_sqlalchemy=True,
            instrument_requests=True,
            instrument_httpx=True,
        )

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

    # --- Auto-wire shutdown
    if auto_wire_shutdown and app is not None:
        try:
            if hasattr(app, "add_event_handler"):
                app.add_event_handler("shutdown", shutdown_tracing)
            elif hasattr(app, "on_event"):
                app.on_event("shutdown")(shutdown_tracing)  # type: ignore[misc]
        except Exception:
            pass

    return shutdown_tracing
