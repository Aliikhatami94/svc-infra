# Operations & Reliability

**svc-infra** provides operational primitives for building resilient, observable services: health probes, circuit breakers, maintenance mode, and SLO-ready metrics.

---

## Quick Start

```python
from fastapi import FastAPI, Depends
from svc_infra.api.fastapi.ops.add import add_probes, add_maintenance_mode
from svc_infra.health import (
    HealthRegistry,
    check_database,
    check_redis,
    add_health_routes,
)

app = FastAPI()

# Add basic ops probes
add_probes(app)

# Add detailed health checks
registry = HealthRegistry()
registry.add("database", check_database(os.getenv("SQL_URL")), critical=True)
registry.add("redis", check_redis(os.getenv("REDIS_URL")), critical=False)
add_health_routes(app, registry)

# Enable maintenance mode gate
add_maintenance_mode(app)
```

---

## Health Probes

Kubernetes-style health probes for container orchestration.

### Basic Probes

`add_probes()` mounts three lightweight endpoints:

```python
from svc_infra.api.fastapi.ops.add import add_probes

add_probes(app, prefix="/_ops")
```

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /_ops/live` | Liveness probe | `{"status": "ok"}` always |
| `GET /_ops/ready` | Readiness probe | `{"status": "ok"}` always |
| `GET /_ops/startup` | Startup probe | `{"status": "ok"}` always |

**Note:** Basic probes always return 200. For dependency-aware probes, use the `HealthRegistry`.

### Detailed Health Checks

For production deployments, register dependency checks:

```python
from svc_infra.health import (
    HealthRegistry,
    check_database,
    check_redis,
    check_url,
    check_tcp,
    add_health_routes,
)

registry = HealthRegistry()

# Critical checks (failure = unhealthy)
registry.add("database", check_database(os.getenv("SQL_URL")), critical=True)

# Non-critical checks (failure = degraded)
registry.add("cache", check_redis(os.getenv("REDIS_URL")), critical=False)

# External service check
registry.add("payment-api", check_url("https://api.stripe.com/v1/health"))

# TCP port check
registry.add("queue", check_tcp("rabbitmq", 5672))

add_health_routes(app, registry)
```

**Endpoints created:**

| Endpoint | Purpose | Status Codes |
|----------|---------|--------------|
| `GET /_health/live` | Liveness (always 200) | 200 |
| `GET /_health/ready` | All checks | 200 (healthy/degraded), 503 (unhealthy) |
| `GET /_health/startup` | Critical checks only | 200, 503 |
| `GET /_health/checks/{name}` | Single check | 200, 503, 404 |

### Health Status Types

```python
from svc_infra.health import HealthStatus

class HealthStatus(StrEnum):
    HEALTHY = "healthy"      # All checks passed
    DEGRADED = "degraded"    # Non-critical checks failed
    UNHEALTHY = "unhealthy"  # Critical checks failed
    UNKNOWN = "unknown"      # Check hasn't run
```

### Health Check Response

```json
{
  "status": "healthy",
  "checks": [
    {"name": "database", "status": "healthy", "latency_ms": 2.5},
    {"name": "cache", "status": "healthy", "latency_ms": 1.2}
  ]
}
```

### Built-in Check Functions

| Function | Description | Example |
|----------|-------------|---------|
| `check_database(url)` | PostgreSQL SELECT 1 | `check_database(os.getenv("SQL_URL"))` |
| `check_redis(url)` | Redis PING | `check_redis(os.getenv("REDIS_URL"))` |
| `check_url(url, **opts)` | HTTP request | `check_url("http://api:8080/health")` |
| `check_tcp(host, port)` | TCP connect | `check_tcp("rabbitmq", 5672)` |

### Custom Health Checks

```python
from svc_infra.health import HealthCheckResult, HealthStatus

async def check_elasticsearch() -> HealthCheckResult:
    """Custom health check for Elasticsearch."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://elasticsearch:9200/_cluster/health")
            data = resp.json()

            if data.get("status") == "green":
                return HealthCheckResult(
                    name="elasticsearch",
                    status=HealthStatus.HEALTHY,
                    latency_ms=resp.elapsed.total_seconds() * 1000,
                    details={"cluster_status": data["status"]},
                )
            elif data.get("status") == "yellow":
                return HealthCheckResult(
                    name="elasticsearch",
                    status=HealthStatus.DEGRADED,
                    latency_ms=resp.elapsed.total_seconds() * 1000,
                    message="Cluster is yellow",
                )
            else:
                return HealthCheckResult(
                    name="elasticsearch",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=resp.elapsed.total_seconds() * 1000,
                    message=f"Cluster status: {data.get('status')}",
                )
    except Exception as e:
        return HealthCheckResult(
            name="elasticsearch",
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            message=str(e),
        )

registry.add("elasticsearch", check_elasticsearch)
```

### Startup Dependency Waiting

Wait for dependencies before accepting traffic:

```python
from svc_infra.health import add_startup_probe, check_database, check_redis

add_startup_probe(
    app,
    checks=[
        check_database(os.getenv("SQL_URL")),
        check_redis(os.getenv("REDIS_URL")),
    ],
    timeout=60.0,   # Wait up to 60 seconds
    interval=2.0,   # Check every 2 seconds
)
```

Or use the registry directly:

```python
@app.on_event("startup")
async def wait_for_deps():
    if not await registry.wait_until_healthy(timeout=60, interval=2):
        result = await registry.check_all()
        failed = [c.name for c in result.checks if c.status != HealthStatus.HEALTHY]
        raise RuntimeError(f"Dependencies not ready: {failed}")
```

### Kubernetes Configuration

```yaml
# deployment.yaml
spec:
  containers:
    - name: app
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
        initialDelaySeconds: 5
        periodSeconds: 5
        failureThreshold: 2
      startupProbe:
        httpGet:
          path: /_health/startup
          port: 8000
        initialDelaySeconds: 10
        periodSeconds: 5
        failureThreshold: 30  # 30 * 5s = 150s max startup
```

---

## Circuit Breaker

Protect against cascading failures with the circuit breaker pattern.

### Basic Usage

```python
from svc_infra.resilience import CircuitBreaker, CircuitBreakerError

breaker = CircuitBreaker(
    name="payment-api",
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=30.0,    # Wait 30s before trying again
    half_open_max_calls=3,    # Allow 3 test calls in half-open
    success_threshold=2,      # 2 successes to close
)

# Context manager usage
async def process_payment(amount: Decimal):
    try:
        async with breaker:
            return await payment_api.charge(amount)
    except CircuitBreakerError as e:
        # Circuit is open, use fallback
        logger.warning(f"Payment circuit open: {e}")
        return await queue_for_retry(amount)
```

### Decorator Usage

```python
@breaker.protect
async def call_external_api():
    """This function is protected by the circuit breaker."""
    return await external_service.call()
```

### Circuit States

```
CLOSED ──(failures >= threshold)──► OPEN
   ▲                                   │
   │                                   │
   │                          (recovery_timeout)
   │                                   │
   │                                   ▼
   └──(successes >= threshold)── HALF_OPEN
```

| State | Behavior |
|-------|----------|
| `CLOSED` | Normal operation, calls pass through |
| `OPEN` | Calls rejected with `CircuitBreakerError` |
| `HALF_OPEN` | Limited test calls allowed |

### Circuit Breaker Statistics

```python
stats = breaker.stats

print(f"Total calls: {stats.total_calls}")
print(f"Successful: {stats.successful_calls}")
print(f"Failed: {stats.failed_calls}")
print(f"Rejected: {stats.rejected_calls}")
print(f"State changes: {stats.state_changes}")
```

### Environment-Based Circuit

For simple use cases, use the environment-controlled dependency:

```python
from svc_infra.api.fastapi.ops.add import circuit_breaker_dependency

# Opens when CIRCUIT_OPEN=1
@app.get("/api/data", dependencies=[Depends(circuit_breaker_dependency())])
async def get_data():
    return await external_api.fetch()
```

Set `CIRCUIT_OPEN=1` to immediately reject all requests with 503.

### Per-Service Breakers

```python
# Create separate breakers for different services
payment_breaker = CircuitBreaker(name="payment", failure_threshold=3)
inventory_breaker = CircuitBreaker(name="inventory", failure_threshold=5)
shipping_breaker = CircuitBreaker(name="shipping", failure_threshold=5)

@payment_breaker.protect
async def charge_payment(amount):
    return await stripe.charges.create(amount=amount)

@inventory_breaker.protect
async def reserve_inventory(items):
    return await inventory_service.reserve(items)
```

---

## Maintenance Mode

Gate write operations during maintenance windows:

```python
from svc_infra.api.fastapi.ops.add import add_maintenance_mode

add_maintenance_mode(
    app,
    env_var="MAINTENANCE_MODE",
    exempt_prefixes=("/_health", "/_ops"),
)
```

**Behavior when `MAINTENANCE_MODE=1`:**
- `GET`, `HEAD`, `OPTIONS` requests pass through
- `POST`, `PUT`, `PATCH`, `DELETE` return 503 with `{"detail": "maintenance"}`
- Exempt prefixes always pass through

### Programmatic Control

```python
import os

# Enable maintenance mode
os.environ["MAINTENANCE_MODE"] = "1"

# Disable maintenance mode
os.environ["MAINTENANCE_MODE"] = ""
```

---

## Route Classification

Classify routes for differentiated SLO tracking:

```python
from svc_infra.obs.add import add_observability

def route_classifier(path: str, method: str) -> str:
    """Classify routes for metrics."""
    if path.startswith("/admin"):
        return "admin"
    elif path.startswith("/api/internal"):
        return "internal"
    elif path.startswith("/_"):
        return "system"
    else:
        return "public"

add_observability(
    app,
    route_classifier=route_classifier,
)
```

Metrics labels encode as `"{base_path}|{class}"` for filtering in dashboards.

---

## SLO Monitoring

### Key Metrics

svc-infra exposes Prometheus metrics for SLO tracking:

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total requests by method, path, status |
| `http_request_duration_seconds` | Histogram | Request latency |
| `http_requests_in_progress` | Gauge | Active requests |

### Availability SLO

```promql
# 99.9% availability (exclude 5xx)
sum(rate(http_requests_total{status!~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

### Latency SLO

```promql
# 99th percentile latency
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)
```

### Error Budget

```promql
# Error budget remaining (target 99.9%)
1 - (
  sum(increase(http_requests_total{status=~"5.."}[30d]))
  /
  sum(increase(http_requests_total[30d]))
) - 0.001
```

---

## Dashboards

### Importing the HTTP Overview Dashboard

```bash
# View dashboard location
ls src/svc_infra/obs/grafana/dashboards/http-overview.json

# Import to Grafana via API
curl -X POST \
  -H "Authorization: Bearer $GRAFANA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @http-overview.json \
  "$GRAFANA_URL/api/dashboards/db"
```

### Dashboard Panels

The bundled dashboard includes:
- **Success Rate (5m)** — Percentage of non-5xx responses
- **P99 Latency** — 99th percentile response time
- **Top Routes by 5xx** — Routes with highest error rates
- **Request Rate** — Requests per second by status code
- **Active Connections** — In-flight requests

---

## Graceful Degradation

### Feature Flags Integration

```python
async def get_recommendations(user_id: str):
    """Degrade gracefully when ML service is down."""
    try:
        async with ml_breaker:
            return await ml_service.get_personalized(user_id)
    except CircuitBreakerError:
        # Fallback to popular items
        return await get_popular_items()
```

### Fallback Responses

```python
from svc_infra.resilience import CircuitBreaker

search_breaker = CircuitBreaker(name="search", failure_threshold=3)

@app.get("/search")
async def search(q: str):
    try:
        async with search_breaker:
            return await elasticsearch.search(q)
    except CircuitBreakerError:
        # Fallback to database search
        return await db_fallback_search(q)
    except Exception:
        # Ultimate fallback
        return {"results": [], "fallback": True}
```

### Dependency Isolation

```python
# Isolate non-critical features
analytics_breaker = CircuitBreaker(
    name="analytics",
    failure_threshold=2,
    recovery_timeout=60.0,
)

@app.post("/order")
async def create_order(order: OrderCreate):
    # Critical path - no circuit breaker
    result = await process_order(order)

    # Non-critical - isolated with circuit breaker
    try:
        async with analytics_breaker:
            await track_order_event(result)
    except CircuitBreakerError:
        pass  # Analytics can fail silently

    return result
```

---

## Production Recommendations

### Probe Configuration

| Probe | Initial Delay | Period | Timeout | Failure Threshold |
|-------|---------------|--------|---------|-------------------|
| Liveness | 5s | 10s | 3s | 3 |
| Readiness | 5s | 5s | 3s | 2 |
| Startup | 10s | 5s | 3s | 30 (= 150s max) |

### Circuit Breaker Tuning

| Parameter | Low Traffic | High Traffic | Notes |
|-----------|-------------|--------------|-------|
| `failure_threshold` | 3-5 | 10-20 | Higher for noisy dependencies |
| `recovery_timeout` | 30-60s | 10-30s | Shorter for quick recovery |
| `half_open_max_calls` | 1-3 | 3-5 | More test calls for confidence |
| `success_threshold` | 1-2 | 2-3 | More successes to confirm recovery |

### Alert Thresholds

```yaml
# alerting-rules.yaml
groups:
  - name: slo-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 0.01
        for: 2m
        labels:
          severity: warning

      - alert: HighLatency
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          ) > 2.0
        for: 5m
        labels:
          severity: warning

      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state{state="open"} == 1
        for: 1m
        labels:
          severity: critical
```

---

## Troubleshooting

### Probes Failing

**Symptom:** Kubernetes restarts pods due to failed probes.

**Diagnosis:**
```bash
# Check probe responses
curl http://localhost:8000/_health/ready
curl http://localhost:8000/_health/startup

# Check individual checks
curl http://localhost:8000/_health/checks/database
```

**Solutions:**
1. Increase probe timeouts if database is slow
2. Check if critical dependencies are actually down
3. Review logs for connection errors
4. Verify environment variables are set correctly

### Circuit Stuck Open

**Symptom:** Circuit breaker never recovers.

**Diagnosis:**
```python
print(f"State: {breaker.state}")
print(f"Remaining timeout: {breaker._remaining_timeout()}")
print(f"Stats: {breaker.stats}")
```

**Solutions:**
1. Check if downstream service is actually healthy
2. Reduce `recovery_timeout` for faster testing
3. Manually reset: `breaker.reset()`
4. Verify `success_threshold` is achievable

### Maintenance Mode Stuck

**Symptom:** Cannot disable maintenance mode.

**Diagnosis:**
```bash
echo $MAINTENANCE_MODE
# Check if multiple env files are loaded
```

**Solutions:**
1. Ensure no secondary env file is setting the variable
2. Restart the application after unsetting
3. Check for deployment config that overrides env vars

---

## API Reference

### add_probes

```python
def add_probes(
    app: FastAPI,
    *,
    prefix: str = "/_ops",
    include_in_schema: bool = False,
) -> None:
    """Mount basic liveness/readiness/startup probes."""
```

### add_health_routes

```python
def add_health_routes(
    app: FastAPI,
    registry: HealthRegistry,
    *,
    prefix: str = "/_health",
    include_in_schema: bool = False,
    detailed_on_failure: bool = True,
) -> None:
    """Add health check routes with dependency checks."""
```

### CircuitBreaker

```python
class CircuitBreaker:
    def __init__(
        self,
        name: str = "default",
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
        failure_exceptions: tuple[type[Exception], ...] = (Exception,),
    ):
        """Create a circuit breaker for protecting external calls."""
```

### HealthRegistry

```python
class HealthRegistry:
    def add(
        self,
        name: str,
        check_fn: HealthCheckFn,
        *,
        critical: bool = True,
        timeout: float = 5.0,
    ) -> None:
        """Register a health check."""

    async def check_all(self) -> AggregatedHealthResult:
        """Run all checks and return aggregated result."""

    async def wait_until_healthy(
        self,
        *,
        timeout: float = 60.0,
        interval: float = 2.0,
    ) -> bool:
        """Wait for all critical checks to pass."""
```

---

## See Also

- [Observability Guide](observability.md) — Metrics and dashboards
- [Timeouts & Resource Limits](timeouts-and-resource-limits.md) — Request timeouts
- [CLI Reference](cli.md) — Health check commands
- [Environment Reference](environment.md) — Configuration options
