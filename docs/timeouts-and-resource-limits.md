# Timeouts & Resource Limits

svc-infra provides comprehensive timeout and resource management to protect your service
from slowloris attacks, runaway handlers, slow dependencies, and cascading failures.

---

## Why Timeouts Matter

Without proper timeouts:

```
Client ──slow upload──────────────────────────> Server (resources consumed)
         ← worker blocked indefinitely ────────────────────────────>
                                                Other requests starve
```

With timeouts:

```
Client ──slow upload────X (408 after 15s)
Server: Resources freed, continues serving other requests
```

---

## Quick Start

### Essential Middleware

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.middleware.timeout import (
    BodyReadTimeoutMiddleware,
    HandlerTimeoutMiddleware,
)
from svc_infra.api.fastapi.middleware.graceful_shutdown import install_graceful_shutdown

app = FastAPI()

# Protect against slowloris uploads
app.add_middleware(BodyReadTimeoutMiddleware)  # Default: 15s prod, 30s dev

# Cap handler execution time
app.add_middleware(HandlerTimeoutMiddleware)  # Default: 30s prod, 15s dev

# Graceful shutdown for in-flight requests
install_graceful_shutdown(app)  # Default: 20s prod, 5s dev
```

---

## Configuration Reference

### Environment Variables

| Variable | Default (prod/nonprod) | Description |
|----------|----------------------|-------------|
| `REQUEST_BODY_TIMEOUT_SECONDS` | 15 / 30 | Max time to read request body |
| `REQUEST_TIMEOUT_SECONDS` | 30 / 15 | Max handler execution time |
| `HTTP_CLIENT_TIMEOUT_SECONDS` | 10.0 | Default outbound HTTP timeout |
| `DB_STATEMENT_TIMEOUT_MS` | unset | PostgreSQL statement timeout |
| `JOB_DEFAULT_TIMEOUT_SECONDS` | unset | Background job timeout |
| `WEBHOOK_DELIVERY_TIMEOUT_SECONDS` | 10.0 | Webhook HTTP delivery timeout |
| `SHUTDOWN_GRACE_PERIOD_SECONDS` | 20.0 / 5.0 | Graceful shutdown wait |

### Environment Detection

Defaults automatically adjust based on environment:

```python
from svc_infra.app.env import pick

timeout = pick(prod=30, nonprod=15)  # 30 in production, 15 otherwise
```

---

## Request Body Timeout (Slowloris Defense)

### BodyReadTimeoutMiddleware

Protects against slowloris attacks by enforcing per-chunk timeouts:

```python
from svc_infra.api.fastapi.middleware.timeout import BodyReadTimeoutMiddleware

app.add_middleware(BodyReadTimeoutMiddleware, timeout_seconds=15)
```

**How it works:**

1. Middleware greedily drains incoming request body
2. Each chunk must arrive within the timeout
3. If timeout expires between chunks → 408 Response
4. Body is buffered and replayed to the handler

**Response on timeout:**

```json
{
  "type": "about:blank",
  "title": "Request Timeout",
  "status": 408,
  "detail": "Timed out while reading request body.",
  "instance": "/api/upload"
}
```

### Tuning for Upload Endpoints

For file upload endpoints, you may need longer timeouts:

```python
# Skip body timeout for upload endpoints
# (Use per-route handling or skip_paths if added in future)

# Alternative: Set longer timeout globally
app.add_middleware(BodyReadTimeoutMiddleware, timeout_seconds=60)
```

---

## Handler Timeout

### HandlerTimeoutMiddleware

Caps total handler execution time to prevent runaway requests:

```python
from svc_infra.api.fastapi.middleware.timeout import HandlerTimeoutMiddleware

app.add_middleware(
    HandlerTimeoutMiddleware,
    timeout_seconds=30,
    skip_paths=["/v1/stream", "/v1/chat/completions"],
)
```

**Response on timeout:**

```json
{
  "type": "about:blank",
  "title": "Gateway Timeout",
  "status": 504,
  "detail": "Handler did not complete within 30s",
  "instance": "/api/slow-endpoint"
}
```

### Skip Paths

Use `skip_paths` for endpoints that legitimately run longer:

```python
app.add_middleware(
    HandlerTimeoutMiddleware,
    timeout_seconds=30,
    skip_paths=[
        "/v1/stream",           # SSE streaming
        "/v1/chat/completions", # LLM responses
        "/v1/export",           # Large exports
        "/ws",                  # WebSocket upgrades
    ],
)
```

**Prefix matching**: `/v1/chat` matches `/v1/chat`, `/v1/chat/stream`, but not `/api/v1/chat`.

---

## Outbound HTTP Timeouts

### Default HTTP Client

Create httpx clients with consistent timeouts:

```python
from svc_infra.http.client import (
    new_async_httpx_client,
    new_httpx_client,
    get_default_timeout_seconds,
)

# Async client
async with new_async_httpx_client() as client:
    response = await client.get("https://api.example.com/data")

# Sync client  
with new_httpx_client() as client:
    response = client.get("https://api.example.com/data")

# Custom timeout
async with new_async_httpx_client(timeout_seconds=5) as client:
    response = await client.get("https://api.example.com/fast-endpoint")
```

### Timeout Configuration

```python
from svc_infra.http.client import make_timeout

# Full timeout object for granular control
timeout = make_timeout(seconds=10)  # Creates httpx.Timeout

# Direct usage
client = httpx.AsyncClient(timeout=timeout)
```

### Error Mapping

When `register_error_handlers(app)` is installed, httpx timeouts are mapped to 504:

```python
from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers

register_error_handlers(app)

# Now httpx.TimeoutException → 504 Gateway Timeout
```

**Response:**

```json
{
  "type": "about:blank",
  "title": "Gateway Timeout",
  "status": 504,
  "detail": "Upstream request timed out",
  "instance": "/api/proxy"
}
```

---

## Database Statement Timeout

### PostgreSQL Timeout

Set per-transaction statement timeout to prevent runaway queries:

```bash
# Environment variable
DB_STATEMENT_TIMEOUT_MS=5000  # 5 seconds
```

**How it works:**

1. On session creation, executes `SET LOCAL statement_timeout = :ms`
2. Query cancelled if it exceeds timeout
3. Non-Postgres dialects (SQLite) skip this safely

### Per-Route Timeouts

For different timeout needs per endpoint:

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def with_timeout(session: AsyncSession, timeout_ms: int):
    await session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))

@app.get("/api/quick-query")
async def quick_query(session: AsyncSession = Depends(get_session)):
    await with_timeout(session, 1000)  # 1 second
    # ... fast query

@app.get("/api/report")
async def report(session: AsyncSession = Depends(get_session)):
    await with_timeout(session, 30000)  # 30 seconds for reports
    # ... complex aggregation
```

---

## Background Job Timeouts

### Job Timeout Configuration

```bash
JOB_DEFAULT_TIMEOUT_SECONDS=300  # 5 minutes
```

The jobs runner wraps handlers with `asyncio.wait_for()`:

```python
from svc_infra.jobs.worker import process_one

# Job will be cancelled if it exceeds timeout
await process_one(queue, handler)  # Uses JOB_DEFAULT_TIMEOUT_SECONDS
```

### Per-Job Timeouts

```python
@job_system.task(timeout=60)  # 60 second timeout for this job
async def quick_job():
    await do_quick_work()

@job_system.task(timeout=3600)  # 1 hour for long-running jobs
async def batch_job():
    await process_all_items()
```

---

## Webhook Delivery Timeout

### Configuration

```bash
WEBHOOK_DELIVERY_TIMEOUT_SECONDS=10
```

Falls back to `HTTP_CLIENT_TIMEOUT_SECONDS` if not set.

### Implementation

```python
from svc_infra.jobs.builtins.webhook_delivery import make_webhook_handler

handler = make_webhook_handler(
    outbox=outbox_store,
    inbox=inbox_store,
    get_webhook_url_for_topic=lambda t: urls[t],
    get_secret_for_topic=lambda t: secrets[t],
)

# Delivery uses timeout from WEBHOOK_DELIVERY_TIMEOUT_SECONDS
```

---

## Graceful Shutdown

### Configuration

```python
from svc_infra.api.fastapi.middleware.graceful_shutdown import install_graceful_shutdown

install_graceful_shutdown(app, grace_seconds=30)
```

Or via environment:

```bash
SHUTDOWN_GRACE_PERIOD_SECONDS=30
```

### How It Works

1. SIGTERM received
2. Health endpoints return unhealthy (load balancer drains traffic)
3. Wait for in-flight requests (up to grace period)
4. Force shutdown after grace period

### Kubernetes Integration

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    livenessProbe:
      httpGet:
        path: /_ops/live
        port: 8000
    readinessProbe:
      httpGet:
        path: /_ops/ready
        port: 8000
    lifecycle:
      preStop:
        exec:
          command: ["sleep", "5"]  # Allow LB to drain
  terminationGracePeriodSeconds: 35  # > SHUTDOWN_GRACE_PERIOD_SECONDS
```

---

## Tuning by Workload

### API Services (General)

```bash
REQUEST_BODY_TIMEOUT_SECONDS=15
REQUEST_TIMEOUT_SECONDS=30
HTTP_CLIENT_TIMEOUT_SECONDS=10
DB_STATEMENT_TIMEOUT_MS=5000
SHUTDOWN_GRACE_PERIOD_SECONDS=20
```

### AI/LLM Services

```bash
REQUEST_BODY_TIMEOUT_SECONDS=30   # Larger prompts
REQUEST_TIMEOUT_SECONDS=120       # LLM generation takes time
HTTP_CLIENT_TIMEOUT_SECONDS=60    # LLM API calls
SHUTDOWN_GRACE_PERIOD_SECONDS=30
```

### File Upload Services

```bash
REQUEST_BODY_TIMEOUT_SECONDS=120  # Large file uploads
REQUEST_TIMEOUT_SECONDS=300       # Processing time
SHUTDOWN_GRACE_PERIOD_SECONDS=60  # Wait for uploads to complete
```

### Batch Processing

```bash
JOB_DEFAULT_TIMEOUT_SECONDS=3600  # 1 hour jobs
DB_STATEMENT_TIMEOUT_MS=300000    # 5 minute queries
SHUTDOWN_GRACE_PERIOD_SECONDS=120 # Wait for batch to checkpoint
```

---

## Timeout Cascading Prevention

### The Problem

```
Client ──(30s timeout)──> API ──(30s timeout)──> Downstream
                          └── Downstream times out at 29.9s
                          └── API processing + response = 30.1s
                          └── Client sees timeout, retries
                          └── Duplicate work!
```

### The Solution: Staggered Timeouts

```python
# Client timeout: 30s
# API handler timeout: 25s
# Downstream HTTP timeout: 10s
# Database timeout: 5s

# Always leave buffer for processing + response
```

**Rule of thumb**: Each layer should timeout faster than its caller.

```bash
# Gateway/Load Balancer: 60s
REQUEST_TIMEOUT_SECONDS=50          # Leave 10s buffer
HTTP_CLIENT_TIMEOUT_SECONDS=10      # Fail fast on dependencies
DB_STATEMENT_TIMEOUT_MS=5000        # Fastest layer
```

### Proxy/Gateway Alignment

Ensure upstream proxy timeouts exceed your app timeouts:

| Layer | Timeout | Rationale |
|-------|---------|-----------|
| NGINX/ALB | 60s | Highest timeout |
| Handler | 50s | Buffer for response |
| HTTP client | 10s | Fail fast, retry |
| Database | 5s | Fastest |

---

## Load Testing

### Timeout Verification

```python
import asyncio
from httpx import AsyncClient

async def test_timeout_behavior():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # Test handler timeout
        try:
            response = await client.get("/api/slow-endpoint", timeout=60)
            assert response.status_code == 504
        except Exception as e:
            print(f"Client timed out: {e}")

        # Test body timeout (slowloris simulation)
        # ... custom slow upload implementation
```

### Concurrent Load

```bash
# Using hey
hey -n 1000 -c 50 -t 60 http://localhost:8000/api/endpoint

# Using wrk with slow script
wrk -t4 -c100 -d30s -s slow-body.lua http://localhost:8000/api/upload
```

---

## Resource Leak Detection

### Symptoms

- Increasing memory over time
- Connection pool exhaustion
- File descriptor leaks

### Prevention

```python
# Always use context managers
async with new_async_httpx_client() as client:
    response = await client.get(url)

# Proper session cleanup
async with async_session_maker() as session:
    result = await session.execute(query)

# Background task cleanup
try:
    await asyncio.wait_for(task, timeout=30)
except TimeoutError:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass  # Expected
```

### Monitoring

```python
import resource

def log_resource_usage():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    logger.info("Resource usage", extra={
        "memory_mb": usage.ru_maxrss / 1024,
        "user_time": usage.ru_utime,
        "system_time": usage.ru_stime,
    })
```

---

## Kubernetes Resource Limits

### Container Resources

```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

### Alignment with Timeouts

```yaml
# If your handler timeout is 30s and you expect max 10 concurrent requests:
# Memory = base + (per_request_memory * max_concurrent)
# CPU = base + (per_request_cpu * max_concurrent)

resources:
  limits:
    memory: "1Gi"   # Ensure enough for burst
    cpu: "1000m"
```

### Liveness vs Readiness

```yaml
livenessProbe:
  httpGet:
    path: /_ops/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5   # Should be < handler timeout
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /_ops/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

---

## Troubleshooting

### 408 Instead of Expected 200

**Cause**: Body timeout triggered before upload completed.

**Solutions**:
1. Increase `REQUEST_BODY_TIMEOUT_SECONDS`
2. Use chunked uploads with progress reporting
3. Skip timeout for upload endpoints

### 504 on Valid Requests

**Cause**: Handler taking too long.

**Solutions**:
1. Optimize slow queries (add indexes, reduce N+1)
2. Add caching
3. Increase handler timeout (if truly needed)
4. Use background jobs for heavy processing

### Client Timeout but Server Continues

**Cause**: Timeout at client/proxy level, not app level.

**Solutions**:
1. Align proxy/gateway timeouts
2. Use cancellation tokens if supported
3. Implement request cancellation handling

### Database Timeout Ignored

**Cause**: Non-Postgres database or timeout not set.

**Check**: `DB_STATEMENT_TIMEOUT_MS` only works with PostgreSQL.

---

## Testing

### Unit Tests

```python
import pytest
from fastapi.testclient import TestClient

def test_body_timeout(client, time_machine):
    """Slow body read should return 408."""
    # This requires custom test infrastructure to simulate slow uploads
    pass

def test_handler_timeout(client):
    """Slow handler should return 504."""
    response = client.get("/api/slow-endpoint")
    assert response.status_code == 504
    assert response.json()["title"] == "Gateway Timeout"

def test_outbound_timeout(client, httpx_mock):
    """Slow downstream should return 504."""
    httpx_mock.add_response(status_code=200)
    httpx_mock.add_callback(lambda r: asyncio.sleep(15))

    response = client.get("/api/proxy")
    assert response.status_code == 504
```

---

## See Also

- [Rate Limiting](rate-limiting.md) — Complement timeouts with request limits
- [Observability](observability.md) — Monitor timeout metrics
- [Ops](ops.md) — Health probes and circuit breakers
