# Acceptance Matrix (A-IDs)

This document maps Acceptance scenarios (A-IDs) to endpoints, CLIs, fixtures, and seed data. Use it to drive the CI promotion gate and local `make accept` runs.

## A0. Harness
- Stack: docker-compose.test.yml (api, db, redis)
- Makefile targets: accept, compose_up, wait, seed, down
- Tests bootstrap: tests/acceptance/conftest.py (BASE_URL), _auth.py, _seed.py, _http.py

## A1. Security & Auth
- A1-01 Register → Verify → Login → /auth/me
  - Endpoints: POST /auth/register, POST /auth/verify, POST /auth/login, GET /auth/me
  - Fixtures: admin, user
- A1-02 Password policy & breach check
  - Endpoints: POST /auth/register
- A1-03 Lockout escalation and cooldown
  - Endpoints: POST /auth/login
- A1-04 RBAC/ABAC enforced
  - Endpoints: GET /admin/*, resource GET with owner guard
- A1-05 Session list & revoke
  - Endpoints: GET/DELETE /auth/sessions
- A1-06 API keys lifecycle
  - Endpoints: POST/GET/DELETE /auth/api-keys, usage via Authorization header
- A1-07 MFA lifecycle
  - Endpoints: /auth/mfa/*

## A2. Rate Limiting
- A2-01 Global limit → 429 with Retry-After
- A2-02 Per-route & tenant override honored
- A2-03 Window reset

## A3. Idempotency & Concurrency
- A3-01 Same Idempotency-Key → identical 2xx
- A3-02 Conflicting payload + same key → 409
- A3-03 Optimistic lock mismatch → 409; success increments version

## A4. Jobs & Scheduling
- A4-01 Custom job consumed
- A4-02 Backoff & DLQ
- A4-03 Cron tick observed

## A5. Webhooks
- A5-01 Producer → delivery (HMAC verified)
- A5-02 Retry stops on success
- A5-03 Secret rotation window accepts old+new

## A6. Tenancy
- A6-01 tenant_id injected on create; list scoped
- A6-02 Cross-tenant → 404/403
- A6-03 Per-tenant quotas enforced

## A7. Data Lifecycle
- A7-01 Soft delete hides; undelete restores
- A7-02 GDPR erasure steps with audit
- A7-03 Retention purge soft→hard
- A7-04 Backup verification healthy

## A8. SLOs & Ops
- A8-01 Metrics http_server_* and db_pool_* present
- A8-02 Maintenance mode 503; circuit breaker trips/recover
- A8-03 Liveness/readiness under DB up/down

## A9. OpenAPI & Error Contracts
- A9-01 /openapi.json valid; examples present
- A9-02 Problem+JSON conforms
- A9-03 Spectral + API Doctor pass

## A10. CLI & DX
- A10-01 DB migrate/rollback/seed
- A10-02 Jobs runner consumes a sample job
- A10-03 SDK smoke-import and /ping

## A22. Storage System
- A22-01 Local backend file upload and retrieval
  - Endpoints: POST /_storage/upload, GET /_storage/download/{filename}
  - Assertions: Upload returns URL, download returns matching content
- A22-02 S3 backend operations (memory backend in acceptance)
  - Endpoints: POST /_storage/upload, GET /_storage/download/{filename}
  - Assertions: Upload succeeds, download returns correct content
- A22-03 Storage backend auto-detection
  - Endpoints: GET /_storage/backend-info, POST /_storage/upload
  - Assertions: Backend detected (MemoryBackend), app.state.storage configured
- A22-04 File deletion and cleanup
  - Endpoints: POST /_storage/upload, DELETE /_storage/files/{filename}, GET /_storage/download/{filename}
  - Assertions: Upload succeeds, delete returns 204, subsequent GET returns 404
- A22-05 Metadata and listing
  - Endpoints: POST /_storage/upload, GET /_storage/list, GET /_storage/metadata/{filename}
  - Assertions: Metadata stored and retrievable, list returns correct keys, prefix filtering works
