# Observability Guide

Production-grade observability with Prometheus metrics, structured logging, health checks, and Grafana dashboards.

## Overview

svc-infra provides comprehensive observability infrastructure:

- **Prometheus Metrics**: HTTP request metrics, histograms, counters
- **Database Metrics**: Connection pool monitoring for SQLAlchemy
- **HTTP Client Metrics**: Outgoing request instrumentation
- **Structured Logging**: JSON format with correlation IDs
- **Health Probes**: Kubernetes-ready liveness/readiness/startup
- **Grafana Dashboards**: Auto-generated dashboards with CLI sync

## Quick Start

### Enable Observability

```python
from svc_infra.api.fastapi.ease import easy_service_app

# Observability enabled by default
app = easy_service_app(name="MyAPI", release="1.0.0")

# Metrics available at /metrics
# Health probes at /_ops/live, /_ops/ready, /_ops/startup
```

Or with explicit control:

```python
from fastapi import FastAPI
from svc_infra.obs.add import add_observability

app = FastAPI()

# Add observability with options
add_observability(
    app,
    db_engines=[engine],  # Optional: SQLAlchemy engines for pool metrics
    metrics_path="/metrics",
    skip_metric_paths=["/metrics", "/health", "/healthz"],
)
```

### Verify It Works

```bash
curl http://localhost:8000/metrics

# Output:
# HELP http_server_requests_total Total HTTP requests
# TYPE http_server_requests_total counter
# http_server_requests_total{method="GET",route="/api/v1/users",code="200"} 42
# ...
```

---

## Prometheus Metrics

### Auto-Instrumented Metrics

svc-infra automatically exposes these metrics:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| \`http_server_requests_total\` | Counter | method, route, code | Total HTTP requests |
| \`http_server_request_duration_seconds\` | Histogram | route, method | Request latency |
| \`http_server_inflight_requests\` | Gauge | route | Concurrent requests |
| \`http_server_response_size_bytes\` | Histogram | route, method | Response body size |
| \`http_server_exceptions_total\` | Counter | route, method | Unhandled exceptions |
| \`http_client_requests_total\` | Counter | method, host, status | Outgoing HTTP requests |
| \`http_client_request_duration_seconds\` | Histogram | method, host | Outgoing request latency |
| \`db_pool_in_use\` | Gauge | pool | Database connections in use |
| \`db_pool_available\` | Gauge | pool | Available connections |
| \`db_pool_checkedout_total\` | Counter | pool | Total checkouts |
| \`db_pool_checkedin_total\` | Counter | pool | Total check-ins |

### Custom Metrics

```python
from svc_infra.obs.metrics.base import counter, gauge, histogram

# Create custom metrics
api_calls = counter(
    "myapp_api_calls_total",
    "Total API calls by endpoint",
    labels=["endpoint", "status"],
)

queue_size = gauge(
    "myapp_queue_size",
    "Current queue size",
    labels=["queue_name"],
)

processing_time = histogram(
    "myapp_processing_seconds",
    "Processing time in seconds",
    labels=["operation"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Use in code
api_calls.labels(endpoint="/users", status="success").inc()
queue_size.labels(queue_name="emails").set(42)
with processing_time.labels(operation="parse").time():
    parse_document(doc)
```

### Histogram Buckets

Default buckets for request duration:

```python
# Default: seconds
(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)

# Configure via environment
METRICS_DEFAULT_BUCKETS="0.01,0.05,0.1,0.25,0.5,1,2.5,5,10"
```

### Label Conventions

Follow Prometheus best practices:

```python
# ✅ Good: Low cardinality, meaningful labels
http_requests_total{method="GET", status="2xx", endpoint="/users"}

# ❌ Bad: High cardinality (unique IDs, timestamps)
http_requests_total{user_id="uuid-123", timestamp="..."}
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| \`ENABLE_OBS\` | \`true\` | Enable observability middleware |
| \`METRICS_ENABLED\` | \`true\` | Enable Prometheus metrics |
| \`METRICS_PATH\` | \`/metrics\` | HTTP path for metrics endpoint |
| \`OBS_SKIP_PATHS\` | \`/metrics,/health,/healthz\` | Paths to exclude from metrics |
| \`SVC_INFRA_DISABLE_PROMETHEUS\` | — | Set to \`1\` to disable entirely |
| \`LOG_LEVEL\` | auto | Log level (DEBUG, INFO, WARNING, ERROR) |
| \`LOG_FORMAT\` | auto | Log format (\`json\` or \`plain\`) |
| \`LOG_DROP_PATHS\` | \`/metrics\` | Paths to exclude from access logs |

### Grafana Cloud Variables

| Variable | Description |
|----------|-------------|
| \`GRAFANA_CLOUD_URL\` | Grafana instance URL (e.g., \`https://your-stack.grafana.net\`) |
| \`GRAFANA_CLOUD_TOKEN\` | API token for dashboard sync |
| \`GRAFANA_CLOUD_PROM_URL\` | Remote write URL for metrics |
| \`GRAFANA_CLOUD_PROM_USERNAME\` | Metrics instance ID |
| \`GRAFANA_CLOUD_RW_TOKEN\` | API token for remote write |
| \`SVC_INFRA_RATE_WINDOW\` | Override \`\$__rate_interval\` in dashboards |
| \`SVC_INFRA_DASHBOARD_REFRESH\` | Dashboard refresh interval (default: \`5s\`) |
| \`SVC_INFRA_DASHBOARD_RANGE\` | Default time range (default: \`now-6h\`) |

---

## Health Endpoints

### Basic Probes

```python
from svc_infra.api.fastapi.ops.add import add_probes

add_probes(app, prefix="/_ops")

# Exposes:
# GET /_ops/live    - Liveness (always 200 if process running)
# GET /_ops/ready   - Readiness (can add dependency checks)
# GET /_ops/startup - Startup probe
```

### Advanced Health Registry

```python
from svc_infra.health import (
    HealthRegistry,
    HealthStatus,
    check_database,
    check_redis,
    check_url,
    check_tcp,
    add_health_routes,
)
import os

# Create registry
registry = HealthRegistry()

# Add checks
registry.add(
    "database",
    check_database(os.getenv("DATABASE_URL")),
    critical=True,  # Service is unhealthy if this fails
    timeout=5.0,
)

registry.add(
    "redis",
    check_redis(os.getenv("REDIS_URL")),
    critical=False,  # Service is degraded but functional
)

registry.add(
    "external_api",
    check_url("http://api.example.com/health", expected_status=200),
    critical=False,
)

registry.add(
    "postgres_port",
    check_tcp("db.example.com", 5432),
    critical=True,
)

# Add routes to FastAPI
add_health_routes(app, registry, prefix="/_health")

# Exposes:
# GET /_health/live   - Always 200
# GET /_health/ready  - Runs all checks
# GET /_health/startup - Runs critical checks
```

### Wait for Dependencies

Block startup until dependencies are ready:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Wait up to 60 seconds for dependencies
    if not await registry.wait_until_healthy(timeout=60, interval=2):
        raise RuntimeError("Dependencies not ready")
    yield

app = FastAPI(lifespan=lifespan)
```

### Custom Health Checks

```python
from svc_infra.health import HealthCheckResult, HealthStatus

async def check_custom_service() -> HealthCheckResult:
    try:
        # Your health check logic
        response = await my_service.ping()
        if response.ok:
            return HealthCheckResult(
                name="custom_service",
                status=HealthStatus.HEALTHY,
                latency_ms=response.latency_ms,
            )
        else:
            return HealthCheckResult(
                name="custom_service",
                status=HealthStatus.DEGRADED,
                latency_ms=response.latency_ms,
                message="Service responding slowly",
            )
    except Exception as e:
        return HealthCheckResult(
            name="custom_service",
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            message=str(e),
        )

registry.add("custom_service", check_custom_service, critical=True)
```

### Kubernetes Integration

```yaml
# deployment.yaml
spec:
  containers:
    - name: api
      livenessProbe:
        httpGet:
          path: /_health/live
          port: 8000
        initialDelaySeconds: 5
        periodSeconds: 10
        failureThreshold: 3

      readinessProbe:
        httpGet:
          path: /_health/ready
          port: 8000
        initialDelaySeconds: 10
        periodSeconds: 5
        failureThreshold: 3

      startupProbe:
        httpGet:
          path: /_health/startup
          port: 8000
        initialDelaySeconds: 5
        periodSeconds: 5
        failureThreshold: 30  # 30 * 5s = 150s max startup
```

---

## Structured Logging

### Setup

```python
from svc_infra.app.logging import setup_logging

# Auto-detects format based on environment
# Production: JSON, Development: Plain
setup_logging()

# Explicit configuration
setup_logging(
    level="INFO",      # DEBUG, INFO, WARNING, ERROR
    fmt="json",        # "json" or "plain"
    drop_paths=["/metrics", "/healthz"],  # Don't log these
)
```

### JSON Log Format

```json
{
  "timestamp": "2025-01-15T10:30:45.123Z",
  "level": "INFO",
  "message": "Request completed",
  "logger": "uvicorn.access",
  "request_id": "req-abc123",
  "method": "GET",
  "path": "/api/v1/users",
  "status": 200,
  "duration_ms": 45.2
}
```

### Log Levels by Environment

| Environment | Default Level | Default Format |
|-------------|---------------|----------------|
| \`local\` | DEBUG | plain |
| \`dev\` | DEBUG | plain |
| \`test\` | INFO | plain |
| \`staging\` | INFO | json |
| \`prod\` | INFO | json |

### Correlation IDs

Request IDs are automatically included for tracing:

```python
from svc_infra.api.fastapi.middleware.request_id import get_request_id

@app.get("/users")
async def list_users():
    request_id = get_request_id()
    logger.info("Listing users", extra={"request_id": request_id})
    return users
```

### Filtering Access Logs

Reduce noise from health checks and metrics:

```bash
# Environment variable
LOG_DROP_PATHS="/metrics,/healthz,/_ops/live"
```

```python
# Programmatic
setup_logging(drop_paths=["/metrics", "/healthz", "/_ops/live"])
```

---

## Grafana Dashboards

### CLI Dashboard Sync

Push pre-built dashboards to Grafana Cloud:

```bash
# Set up environment
export GRAFANA_CLOUD_URL="https://your-stack.grafana.net"
export GRAFANA_CLOUD_TOKEN="glsa_..."

# Push dashboards
svc-infra obs dashboard push
```

### Local Development Stack

Start local Grafana + Prometheus:

```bash
# Start observability stack
svc-infra obs-up

# Open:
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090

# Stop when done
svc-infra obs-down
```

### Included Dashboards

svc-infra includes pre-built dashboards:

1. **Service Overview (RED)**: Request rate, errors, duration
2. **Resource Utilization (USE)**: CPU, memory, connections
3. **Database Pool**: Connection pool health
4. **API Endpoints**: Per-route latencies and error rates

### Custom Dashboard Variables

```bash
# Override rate window (default: \$__rate_interval)
SVC_INFRA_RATE_WINDOW="5m"

# Dashboard refresh rate
SVC_INFRA_DASHBOARD_REFRESH="10s"

# Default time range
SVC_INFRA_DASHBOARD_RANGE="now-24h"
```

### Programmatic Dashboard Push

```python
from svc_infra.obs.cloud_dash import push_dashboards_from_pkg

push_dashboards_from_pkg(
    base_url=os.getenv("GRAFANA_CLOUD_URL"),
    token=os.getenv("GRAFANA_CLOUD_TOKEN"),
    folder_title="Service Infrastructure",
)
```

---

## Database Metrics

### SQLAlchemy Pool Metrics

```python
from svc_infra.obs.metrics.sqlalchemy import bind_sqlalchemy_pool_metrics

# Bind metrics to engine(s)
bind_sqlalchemy_pool_metrics(engine)

# Metrics exposed:
# db_pool_size - Configured pool size
# db_pool_checkedout - Currently checked out connections
# db_pool_overflow - Overflow connections in use
# db_pool_checkedout_total - Total checkouts (counter)
# db_pool_checkedin_total - Total check-ins (counter)
```

### Automatic Binding

When using \`add_observability()\`:

```python
add_observability(
    app,
    db_engines=[engine1, engine2],  # Pass your engines
)
```

---

## HTTP Client Metrics

### Automatic Instrumentation

```python
from svc_infra.obs.metrics.http import instrument_httpx, instrument_requests

# Instrument httpx (async)
instrument_httpx()

# Instrument requests (sync)
instrument_requests()

# Now all HTTP clients emit metrics:
# http_client_requests_total{method="GET", host="api.example.com", status="200"}
# http_client_request_duration_seconds{method="GET", host="api.example.com"}
```

---

## Multiprocess Mode

For Gunicorn with multiple workers:

```bash
# Set multiprocess directory
export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

# Ensure directory exists and is writable
mkdir -p \$PROMETHEUS_MULTIPROC_DIR
```

```python
# svc-infra automatically detects and uses MultiProcessCollector
from svc_infra.obs.metrics.base import registry

# Registry handles multiprocess aggregation
```

---

## Production Recommendations

### Metric Cardinality

Avoid high-cardinality labels:

```python
# ❌ Bad: User IDs create unbounded cardinality
http_requests_total{user_id="..."}

# ✅ Good: Use bounded categories
http_requests_total{user_tier="free|pro|enterprise"}
```

### Sampling Strategies

For high-throughput services, consider sampling:

```python
import random

# Sample 10% of requests for detailed metrics
if random.random() < 0.1:
    detailed_metric.observe(value)
```

### Retention Policies

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

# Grafana Cloud retention is based on your plan
# Local Prometheus: configure storage.tsdb.retention.time
```

### Alert Rules

Example Prometheus alerting rules:

```yaml
groups:
  - name: svc-infra
    rules:
      - alert: HighErrorRate
        expr: rate(http_server_requests_total{code=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected

      - alert: SlowResponses
        expr: histogram_quantile(0.99, rate(http_server_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: P99 latency exceeds 2 seconds

      - alert: DatabasePoolExhausted
        expr: db_pool_checkedout / db_pool_size > 0.9
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: Database connection pool nearly exhausted
```

---

## Troubleshooting

### Missing Metrics

```
curl http://localhost:8000/metrics returns 404
```

**Solutions:**
1. Verify \`ENABLE_OBS=true\` or \`METRICS_ENABLED=true\`
2. Check \`SVC_INFRA_DISABLE_PROMETHEUS\` is not set to \`1\`
3. Ensure \`prometheus-client\` is installed: \`pip install svc-infra[metrics]\`

### High Cardinality Warning

```
prometheus: high cardinality on metric http_server_requests_total
```

**Solutions:**
1. Check for dynamic path parameters being used as labels
2. Use route templates, not actual paths: \`/users/{id}\` not \`/users/12345\`
3. Review custom metrics for unbounded label values

### Metrics Not Updating

```
Metrics show stale values
```

**Solutions:**
1. Verify Prometheus is scraping: check \`/targets\` in Prometheus UI
2. Check scrape interval configuration
3. For multiprocess: ensure \`PROMETHEUS_MULTIPROC_DIR\` is writable

### Health Check Timeouts

```
/_health/ready returns 503 after long delay
```

**Solutions:**
1. Increase check timeouts: \`registry.add("db", check, timeout=10.0)\`
2. Review dependency health (database, Redis, external APIs)
3. Use \`critical=False\` for non-essential dependencies

### Log Format Issues

```
Logs appearing in wrong format
```

**Solutions:**
1. Set \`LOG_FORMAT=json\` explicitly for production
2. Check \`ENV\` environment variable is set correctly
3. Call \`setup_logging()\` early in application startup

---

## See Also

- [Ops Guide](ops.md) - SLOs, circuit breakers, maintenance mode
- [Environment Reference](environment.md) - All observability environment variables
- [API Framework](api.md) - FastAPI integration details
- [Health Checks](ops.md#health-probes) - Kubernetes probe patterns
