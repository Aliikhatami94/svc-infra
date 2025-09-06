# Observability (metrics + tracing)

Production-ready observability with one-call setup for FastAPI applications.

`svc_infra.observability` provides:
- Prometheus metrics (ASGI middleware + `/metrics` route)
- OpenTelemetry tracing (OTLP gRPC/HTTP, FastAPI/SQLAlchemy/requests/httpx auto-instrumentation)
- DB pool metrics for SQLAlchemy
- Graceful shutdown hook that flushes spans

## Quick start (FastAPI)

```python
from fastapi import FastAPI
from svc_infra.observability import ObservabilitySettings, add_prometheus, setup_tracing
from svc_infra.observability import bind_sqlalchemy_pool_metrics
from svc_infra.db.manage import make_crud_router_plus

app = FastAPI()
engine = make_crud_router_plus()  # optional
obs = ObservabilitySettings()

# Enable metrics
if obs.METRICS_ENABLED:
    add_prometheus(app, path=obs.METRICS_PATH)

# Enable tracing
if obs.OTEL_ENABLED:
    setup_tracing(
        app=app,
        service_name=obs.OTEL_SERVICE_NAME,
        endpoint=obs.OTEL_EXPORTER_OTLP_ENDPOINT,
        protocol=obs.OTEL_EXPORTER_PROTOCOL,
        sample_ratio=obs.OTEL_SAMPLER_RATIO,
    )

# Optional: DB pool metrics
bind_sqlalchemy_pool_metrics(engine, labels={"db": "primary"})
```

## What you get

### Metrics (/metrics)
- `http_server_requests_total{method,route,code}`
- `http_server_request_duration_seconds_bucket{route,method,le}`
- `http_server_in_flight_requests{route}`
- `db_pool_in_use{db}`, `db_pool_available{db}`
- `db_pool_checkedout_total{db}`

### Tracing (OpenTelemetry)
- Resource attributes: `service.name`, `service.version`, `deployment.environment`, `service.instance.id`
- Propagators: W3C TraceContext + B3 (multi), W3C baggage
- Auto-instrumentation for FastAPI, SQLAlchemy, requests, httpx

## Configuration (environment variables)

| Variable | Default | Notes |
|----------|---------|-------|
| `METRICS_ENABLED` | `true` | Set `false` to disable metrics |
| `METRICS_PATH` | `/metrics` | Override metrics route |
| `METRICS_DEFAULT_BUCKETS` | `(0.005,..,10.0)` | Histogram buckets (seconds) |
| `OTEL_ENABLED` | `true` | Set `false` to disable tracing |
| `OTEL_SERVICE_NAME` | `service` | Service name |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP collector endpoint |
| `OTEL_EXPORTER_PROTOCOL` | `grpc` | `grpc` or `http/protobuf` |
| `OTEL_SAMPLER_RATIO` | `0.1` | 0.0–1.0 |
| `PROMETHEUS_MULTIPROC_DIR` | (unset) | Enable multi-process metrics in Gunicorn/Uvicorn workers |

**Gunicorn note**: Set `PROMETHEUS_MULTIPROC_DIR` to a writable directory (tmpfs works) to aggregate metrics across workers.

## Installation

Install optional dependencies via extras:

```bash
pip install "svc-infra[observability]"        # prometheus-client + opentelemetry deps
# or split if you prefer:
pip install "svc-infra[metrics]"
pip install "svc-infra[tracing]"
```

## Templates

We ship ready-to-use templates under `svc_infra/observability/templates/`:

- `grafana_dashboard.json` - RED metrics for API, USE metrics for DB pools
- `prometheus_rules.yml` - HighErrorRate, HighLatencyP95, DBPoolSaturation alerts
- `otel-collector.yaml` - OTLP receiver, logging exporter; examples for Tempo/Prometheus remote write

## Production configuration

Common production environment variables:

```bash
export OTEL_ENABLED=true
export OTEL_SERVICE_NAME=payments
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export PROMETHEUS_MULTIPROC_DIR=/var/run/prom-mp
```

## Advanced usage

### Custom metrics

```python
from svc_infra.observability import counter, histogram

jobs_total = counter("jobs_total", "Total jobs processed", ["status"])
job_latency = histogram("job_duration_seconds", "Job duration", buckets=[0.1,0.5,1,2,5])

def handle_job(job):
    with job_latency.time():
        try:
            # do work...
            jobs_total.labels("ok").inc()
        except Exception:
            jobs_total.labels("error").inc()
            raise
```

### HTTP client instrumentation

```python
from svc_infra.observability import instrument_requests, instrument_httpx

# Automatically add metrics for all HTTP requests
instrument_requests()   # for requests library
instrument_httpx()      # for httpx library
```

### Histogram bucket tuning

Aim buckets around SLOs; e.g., 5–50–250–1000ms for latency SLO=300ms:

```python
from svc_infra.observability import ObservabilitySettings

# Override via environment
# METRICS_DEFAULT_BUCKETS="0.005,0.01,0.025,0.05,0.1,0.25,0.5,1.0"
```
