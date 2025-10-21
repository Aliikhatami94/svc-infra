# Timeouts & Resource Limits

This guide covers request/handler timeouts, outbound HTTP client timeouts, database statement timeouts, job/webhook delivery timeouts, and graceful shutdown. It explains defaults, configuration, wiring, and recommended tuning by environment.

## Why timeouts?

- Protects your service from slowloris uploads and hanging requests
- Limits blast radius of slow downstreams (HTTP, DB, webhooks)
- Enables predictable backpressure and faster recovery during incidents

## Configuration overview

The library exposes simple environment variables with sensible defaults. Use floats for second values unless noted.

- REQUEST_BODY_TIMEOUT_SECONDS (int)
  - Default: prod=15, nonprod=30
  - Purpose: Abort slow request body reads (slowloris defense)
- REQUEST_TIMEOUT_SECONDS (int)
  - Default: prod=30, nonprod=15
  - Purpose: Cap overall handler execution time
- HTTP_CLIENT_TIMEOUT_SECONDS (float)
  - Default: 10.0
  - Purpose: Default timeout for outbound httpx clients created via helpers
- DB_STATEMENT_TIMEOUT_MS (int)
  - Default: unset (disabled)
  - Purpose: Per-transaction statement timeout (Postgres via SET LOCAL)
- JOB_DEFAULT_TIMEOUT_SECONDS (float)
  - Default: unset (disabled)
  - Purpose: Caps per-job handler runtime in the in-process jobs runner
- WEBHOOK_DELIVERY_TIMEOUT_SECONDS (float)
  - Default: falls back to HTTP client default (10.0)
  - Purpose: Timeout for webhook delivery HTTP calls
- SHUTDOWN_GRACE_PERIOD_SECONDS (float)
  - Default: prod=20.0, nonprod=5.0
  - Purpose: Wait time for in-flight requests to drain on shutdown

See ADR-0010 for design rationale: `src/svc_infra/docs/adr/0010-timeouts-and-resource-limits.md`.

## Request/handler timeouts (FastAPI)

Two middlewares enforce timeouts inside your ASGI app:

- BodyReadTimeoutMiddleware
  - Enforces a per-chunk timeout while reading the incoming request body.
  - If reads stall beyond the timeout, responds with 408 application/problem+json.
  - Module: `svc_infra.api.fastapi.middleware.timeout.BodyReadTimeoutMiddleware`
- HandlerTimeoutMiddleware
  - Caps overall request handler execution time using asyncio.wait_for.
  - If exceeded, responds with 504 application/problem+json.
  - Module: `svc_infra.api.fastapi.middleware.timeout.HandlerTimeoutMiddleware`

Example wiring:

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.middleware.timeout import (
    BodyReadTimeoutMiddleware,
    HandlerTimeoutMiddleware,
)

app = FastAPI()

# Abort slow uploads (slowloris) after 15s in prod / 30s nonprod by default
app.add_middleware(BodyReadTimeoutMiddleware)  # or timeout_seconds=20

# Cap total handler time (e.g., 30s in prod by default)
app.add_middleware(HandlerTimeoutMiddleware)  # or timeout_seconds=25
```

HTTP semantics:

- Body timeout → 408 Request Timeout (Problem+JSON) with fields: type, title, status, detail, instance, trace_id
- Handler timeout → 504 Gateway Timeout (Problem+JSON) with fields: type, title, status, detail, instance, trace_id

## Outbound HTTP client timeouts (httpx)

Use the provided helpers to create httpx clients with the default timeout (driven by HTTP_CLIENT_TIMEOUT_SECONDS).

- Module: `svc_infra.http.client`
  - `get_default_timeout_seconds()` → float
  - `make_timeout(seconds=None) -> httpx.Timeout`
  - `new_httpx_client(timeout_seconds=None, ...) -> httpx.Client`
  - `new_async_httpx_client(timeout_seconds=None, ...) -> httpx.AsyncClient`

Error mapping:

- `httpx.TimeoutException` is mapped to 504 Gateway Timeout with Problem+JSON by default when `register_error_handlers(app)` is used.
  - Module: `svc_infra.api.fastapi.middleware.errors.handlers.register_error_handlers`

## Database statement timeouts (SQLAlchemy / Postgres)

If `DB_STATEMENT_TIMEOUT_MS` is set and Postgres is used, a per-transaction `SET LOCAL statement_timeout = :ms` is executed for sessions yielded by the built-in dependency.

- Module: `svc_infra.api.fastapi.db.sql.session.get_session`
- Non-Postgres dialects (e.g., SQLite) ignore this gracefully.

## Jobs and webhooks

- Jobs runner
  - Env: `JOB_DEFAULT_TIMEOUT_SECONDS`
  - Module: `svc_infra.jobs.worker.process_one` — wraps job handler with `asyncio.wait_for()` when configured.
- Webhook delivery
  - Env: `WEBHOOK_DELIVERY_TIMEOUT_SECONDS` (falls back to HTTP client default when unset)
  - Module: `svc_infra.jobs.builtins.webhook_delivery.make_webhook_handler` — uses `new_async_httpx_client` with derived timeout.

## Graceful shutdown

Install graceful shutdown to wait for in-flight requests (up to a grace period) during application shutdown.

- Module: `svc_infra.api.fastapi.middleware.graceful_shutdown.install_graceful_shutdown`
- Env: `SHUTDOWN_GRACE_PERIOD_SECONDS` (prod=20.0, nonprod=5.0 by default)

```python
from svc_infra.api.fastapi.middleware.graceful_shutdown import install_graceful_shutdown

install_graceful_shutdown(app)  # or grace_seconds=30.0
```

## Tuning recommendations

- Production
  - REQUEST_BODY_TIMEOUT_SECONDS: 10–20s (shorter for public APIs)
  - REQUEST_TIMEOUT_SECONDS: 20–30s (align with upstream proxy/gateway timeouts)
  - HTTP_CLIENT_TIMEOUT_SECONDS: 3–10s (favor quick failover with retries)
  - DB_STATEMENT_TIMEOUT_MS: set per-route/transaction if queries are constrained
  - SHUTDOWN_GRACE_PERIOD_SECONDS: 20–60s depending on peak latencies
- Staging/Dev
  - Relax timeouts slightly to reduce test flakiness (defaults already reflect this)
- Gateways/Proxies
  - Ensure upstream (e.g., NGINX, ALB) timeouts exceed app’s body timeout and are aligned with handler timeout to avoid double timeouts.

## Testing and acceptance

- Unit tests cover body read timeout, handler timeout, outbound timeout mapping, and a smoke check for DB statement timeout.
- Acceptance tests:
  - A2-04: slow handler → 504 Problem
  - A2-05: slow body → 408 Problem or 413 (size) as applicable
  - A2-06: outbound httpx timeout → 504 Problem

## Troubleshooting

- Seeing 200 instead of 408 for slow uploads under some servers?
  - Some servers buffer the entire body before invoking the app. The BodyReadTimeoutMiddleware greedily drains with per-chunk timeouts and replays to reliably detect slowloris. Ensure HTTP/1.1 parsing with a streaming-capable server implementation (e.g., uvicorn+httptools) in acceptance tests.
- Outbound timeouts not mapped to Problem?
  - Ensure `register_error_handlers(app)` is installed so `httpx.TimeoutException` returns a 504 Problem.
- Statement timeout ignored on SQLite?
  - Expected. Non-Postgres dialects skip `SET LOCAL` safely.
