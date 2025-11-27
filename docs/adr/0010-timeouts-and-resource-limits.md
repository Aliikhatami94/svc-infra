# ADR 0010: Timeouts & Resource Limits (A2)

## Context
Services need consistent, configurable timeouts to protect against slowloris/body drip attacks, expensive handlers, slow downstreams, and long-running DB statements. Today we lack unified settings and middleware behavior; some httpx usages hard-code timeouts. We also want consistent Problem+JSON semantics for timeout errors.

## Decision
Introduce environment-driven timeouts and wire them via FastAPI middlewares and helper factories:

- Request body read timeout: aborts slow body streaming (e.g., slowloris) with 408 Request Timeout.
- Overall request timeout: caps handler execution time and returns 504 Gateway Timeout.
- httpx client defaults: central helpers that pick a sane default timeout from env.
- DB statement timeout: future work (PG: SET LOCAL statement_timeout; SQLite/dev: asyncio.wait_for wrapper). Scoped in follow-ups.
 - Graceful shutdown: track in-flight HTTP requests and wait up to grace period; provide worker runner with stop/grace.

## Configuration
Environment variables (with suggested defaults):

- REQUEST_BODY_TIMEOUT_SECONDS: int, default 15 (prod), 30 (non-prod)
- REQUEST_TIMEOUT_SECONDS: int, default 30 (prod), 15 (non-prod)
- HTTP_CLIENT_TIMEOUT_SECONDS: float, default 10.0

These are read at process start. Services can override per-env.

## Behavior
- Body read timeout → 408 application/problem+json with title "Request Timeout"; optional Retry-After not included by default.
- Handler timeout → 504 application/problem+json with title "Gateway Timeout"; include request trace_id in body if present.
- Errors use existing problem_response helper.

## Placement
- Middlewares under svc_infra.api.fastapi.middleware.timeout
- Wiring in svc_infra.api.fastapi.setup._setup_middlewares (after RequestId, before error catching).
- httpx helpers under svc_infra.http.client: new_httpx_client/new_async_httpx_client with env-driven defaults.
 - Graceful shutdown under svc_infra.api.fastapi.middleware.graceful_shutdown and svc_infra.jobs.runner.WorkerRunner.

## Alternatives Considered
- Starlette TimeoutMiddleware: version support/behavior varies; custom middleware gives us consistent Problem+JSON and finer control across environments.

## Consequences
- Adds two middlewares to every app created via setup_service_api/easy_service_app.
- Minor overhead per request; mitigated by simple asyncio.wait_for usage.

## Follow-ups
- PG statement timeout integration; SQLite/dev wrapper.
- Jobs/webhook runner per-job timeout.
 - Graceful shutdown drainage hooks for servers/workers.
- Acceptance tests A2-04..A2-06 per PLANS.

## Change log
- 2025-10-21: Finalized httpx helpers design and placement; proceed to implementation.

---
 Status: Accepted
Date: 2025-10-21
Related: PLANS A2 — Timeouts & Resource Limits
