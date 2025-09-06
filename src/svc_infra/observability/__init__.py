from .settings import ObservabilitySettings
from .metrics.asgi import add_prometheus
from .metrics.http import instrument_requests, instrument_httpx
from .metrics.sqlalchemy import bind_sqlalchemy_pool_metrics
from .tracing.setup import setup_tracing

def enable_observability(app=None, *, service_version=None, deployment_env=None):
    cfg = ObservabilitySettings()
    if cfg.METRICS_ENABLED and app is not None:
        add_prometheus(app, path=cfg.METRICS_PATH)
    if cfg.OTEL_ENABLED:
        setup_tracing(
            service_name=cfg.OTEL_SERVICE_NAME,
            endpoint=cfg.OTEL_EXPORTER_OTLP_ENDPOINT,
            protocol=cfg.OTEL_EXPORTER_PROTOCOL,
            sample_ratio=cfg.OTEL_SAMPLER_RATIO,
            service_version=service_version,
            deployment_env=deployment_env,
        )
    # always safe to call; no-ops if libs missing
    try: instrument_requests()
    except Exception: pass
    try: instrument_httpx()
    except Exception: pass