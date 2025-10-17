# Production Readiness Punch List (v1 Framework Release)

Comprehensive checklist for making the framework production-ready. Each section has structured subtasks: Research → Design → Implement → Tests → Verify → Docs. We will not implement until reviewed; existing functionality will be reused (skipped) when discovered during research.

## Legend
- [ ] Pending
- [x] Completed
- [~] Skipped (already exists / out of scope)
(note) Commentary or link to ADR / PR.

---
## Must-have (Ship with v1)

### 1. Security & Auth Hardening
- [x] Research: audit existing auth, password handling, session storage, roles. (roles_router, RequireRoles, MFA, API key, OAuth scaffolding present; security headers implemented; password policy module exists; refresh token encryption template present)
- [x] Design: ADR for password hashing, token model (access/refresh), RBAC schema, audit log hash-chain. (ADR 0001)
- [x] Implement: password policy & validator. (validate_password + tests committed)
- [x] Implement: breach password check (HIBP range query integration / toggle). (hibp client + validator hook)
- [x] Implement: account lockout service (compute_lockout + FailedAuthAttempt + login hook + tests)
- [x] Implement: session/device table (list + revoke endpoints). (router integrated; negative ownership test added)
- [x] Implement: session/device table (model scaffolding added in security.models: AuthSession)
- [x] Implement: refresh-token rotation & revocation list. (issue + rotate wired in OAuth refresh; revocation entries recorded; tests passing)
- [x] Implement: RBAC decorators + permission registry. (security.permissions + tests)
- [x] Implement: ABAC predicate hook (resource-level attributes). (RequireABAC, owns_resource, enforce_abac + tests)
- [x] Implement: org/team membership & invitations (tokens, expiry, resend). (models + helpers + tests)
- [x] Implement: signed cookies helper. (HMAC-based signer/verify with key rotation + tests)
- [x] Implement: security headers middleware (baseline done).
- [x] Implement: strict CORS defaults with allowlist config. (default deny; env/param allowlist)
- [x] Implement: secret management abstraction + rotation API. (RotatingJWTStrategy with old_secrets support)
- [x] Implement: JWT/crypto key rolling script (dual key validity window). (config via AUTH_JWT__OLD_SECRETS and tests)
- [x] Implement: audit log model (append-only + hash chain field). (AuditLog + compute_audit_hash + append_audit_event + service wrapper + tests)
- [x] Implement: easy-setup helpers (add/setup/ease) for one-line integration. (see api.fastapi.auth.add.add_auth_users and security.add)
- [x] Tests: password policy + lockout (cooldown escalation).
- [x] Tests: session revocation + RBAC enforcement.
- [x] Tests: breach password rejection & pass cases with stubbed checker.
- [x] Tests: audit log hash-chain integrity (tamper detection). (security.audit + test_audit_log_chain)
- [x] Verify: run security marker tests. (auth + security suites passing as of 2025-10-14)
- [x] Docs: security configuration & examples. (see docs/security.md)

### 2. Rate Limiting & Abuse Protection
- [x] Research: confirm no existing rate limiter. (basic middleware existed; refactored to pluggable store)
- [x] Design: Redis bucket schema (lua vs atomic), config surface. (implemented fixed-window atomic INCR)
- [x] Implement: core token bucket / leaky bucket. (in-memory store abstraction)
- [x] Implement: per-route decorators & global middleware. (middleware + dependency factory)
- [x] Implement: 429 Retry-After logic. (headers in 429 + OpenAPI conventions already present)
- [x] Implement: request size & body parse timeout guard. (size limit middleware; parse timeout TBD)
- [x] Implement: basic bot/DoS heuristic metrics hook. (metrics hooks + middleware emits)
- [x] Implement: easy-setup helper for wiring global/per-route rate limits. (integrated via setup_service_api/easy_service_api)
- [x] Tests: bucket depletion/reset, per-route override, Retry-After presence. (tests added)
- [x] Verify: rate limiting test marker. (`-m ratelimit` available; auto-tagged tests)
- [x] Docs: usage & tuning. (see docs/rate-limiting.md)

### 3. Idempotency & Concurrency Controls
- [x] Research: scan for existing idempotency usage or version columns. (found existing middleware; extended)
- [x] Design: idempotency storage abstraction + request hash + 409 conflict semantics; TTL cleanup via lazy expiry.
- [x] Implement: idempotency middleware with pluggable store (in-memory + Redis) and response envelope caching.
- [x] Implement: optimistic locking (version columns) + conflict exception.
- [x] Implement: transactional outbox (in-memory store) + relay skeleton API. (SQL impl TBD)
- [x] Implement: inbox pattern (in-memory dedupe store with TTL). (SQL impl TBD)
- [x] Implement: easy-setup helper to enable idempotency middleware/inbox/outbox. (integrated via setup_service_api/easy_service_api)
- [x] Tests: idempotent replay and conflict on mismatched payload (concurrency marker added).
- [x] Verify: idempotency tests selectable via marker (`-m concurrency`).
- [x] Docs: idempotency middleware usage & semantics. (see docs/idempotency.md)
- [x] Tests: optimistic locking scenarios (version mismatch → 409).
- [x] Tests: outbox enqueue/fetch/mark processed; inbox dedupe.
- [x] Verify: concurrency suite covers optimistic locking and outbox/inbox. (`-m concurrency` green)
- [x] Docs: optimistic locking + outbox/inbox patterns & pitfalls. (see docs/idempotency.md)

### 4. Background Jobs & Scheduling
- [x] Research: existing job queue/scheduler utilities. (note) Chose Redis as production queue backend (visibility timeout + ZSET/HASH), with in-memory queue/scheduler for local/dev; simple interval scheduler over full cron initially.
- [x] Design: Job schema, retry/backoff strategy, cron config format (YAML/DB). (ADR 0002) Job{id, name, payload, available_at, attempts, max_attempts, backoff_seconds, last_error}; exponential backoff base*attempts; DLQ after max_attempts; interval scheduler with next_run_at; future cron loader from YAML.
 - [x] Implement: JobQueue abstraction (Redis) with retry, backoff, DLQ. (RedisJobQueue + tests)
 - [x] Implement: cron scheduler loader & execution loop. (env JSON loader + `svc-infra jobs run` loop)
 - [x] Implement: outbox processor job. (built-in tick to enqueue one message per tick)
 - [x] Implement: webhook delivery worker integration. (signed delivery, inbox dedupe, retry/backoff)
 - [x] Tests: enqueue/dequeue, retry/backoff, cron triggers, DLQ path. (tests/jobs/* incl. fakeredis and CLI)
- [x] Verify: job test marker. (tests/jobs/* using in-memory queue and scheduler pass under -m jobs)
 - [x] Docs: job authoring guide. (see docs/jobs.md)
- [x] Implement: easy-setup helper to choose queue and start scheduler. (see jobs/easy.py)

### 5. Webhooks Framework
- [x] Research: existing webhook verification logic. (note) Use HMAC-SHA256 over canonical JSON; header X-Signature; reuse outbox/jobs for delivery.
- [x] Design: event schema versioning, signature, retry schedule doc. (ADR 0003)
- [x] Implement: producer API & persistence model. (WebhookService + InMemoryWebhookSubscriptions publishing to outbox)
- [x] Implement: HMAC signing & verification middleware. (sign/verify helpers + FastAPI require_signature)
- [x] Implement: retry/backoff logic with tracking fields. (delivery headers include attempt and versioning; retries via JobQueue)
- [x] Implement: secret rotate & test-fire endpoints. (verify_any supports rotation; router exposes /_webhooks/test-fire)
- [x] Tests: signature validation, retry escalation, version handling. (unit + e2e under -m webhooks)
- [x] Verify: webhook test marker. (pyproject marker added)
- [x] Docs: integration guide. (see docs/webhooks.md)
- [x] Implement: easy-setup helper to add webhook producer/verify middleware. (see webhooks/add.py)

### 6. Tenancy
- [x] Research: tenant_id coverage across existing models (payments models, audit/session models, SQL/Mongo scaffolds; enforcement gaps in generic SQL service/routers now addressed).
- [x] Design: BaseModelTenant mixin & query filter enforcement strategy. (ADR-0004 tenancy model & enforcement primitives)
- [x] Implement: request dependency for tenant resolution. (tenancy.context: resolve_tenant_id, require_tenant_id, TenantId, OptionalTenantId)
- [x] Implement: add_tenancy helper to wire resolver hook. (api.fastapi.tenancy.add)
- [x] Implement: tenant-aware CRUD wiring via SqlResource. (SqlResource.tenant_field + make_tenant_crud_router_plus_sql)
 - [x] Implement: per-tenant quotas & rate limit overrides.
- [x] Implement: export tenant CLI.
- [x] Tests: tenant isolation (queries) via TenantSqlService wrapper and context resolver. (tests/tenancy/*)
- [x] Tests: tenant-aware CRUD router behavior (scoped list, injected tenant_id on create, cross-tenant 404). (tests/tenancy/test_tenant_crud_router.py)
 - [x] Tests: rate limits per-tenant; export correctness.
- [x] Verify: tenancy test marker.
- [x] Docs: isolation strategy (soft vs schema vs dedicated DB). (see docs/tenancy.md)
- [x] Implement: easy-setup helper for tenant resolution and tenant-aware CRUD. (see api.fastapi.tenancy.add.add_tenancy and SQL router wiring)

### 7. Data Lifecycle
- [x] Research: migrations tooling & soft delete usage. (repo soft-delete filtering in `src/svc_infra/db/sql/repository.py`; model scaffolding for `deleted_at` in `src/svc_infra/db/sql/scaffold.py`; lifecycle helper in `src/svc_infra/data/add.py`; migrations & `sql-seed` in `src/svc_infra/cli/cmds/db/sql/alembic_cmds.py`)
- [x] Design: soft delete pattern & retention registry. (ADR-0005)
- [x] Implement: migrator CLI (status/apply/rollback/seed). (seed via sql-seed command)
- [x] Implement: fixture/reference loader (idempotent). (see data/fixtures.py and add_data_lifecycle async support)
- [x] Implement: GDPR erasure workflow (queued + audit entry). (see data/erasure.py with ErasurePlan/Step and audit hook)
- [x] Implement: retention purge job. (see data/retention.py with RetentionPolicy + run_retention_purge)
- [x] Implement: backup verification (PITR job). (see data/backup.py make_backup_verification_job)
	- [x] Stub: backup health report + simple verifier (see data/backup.py)
- [x] Tests: soft delete filter, erasure pipeline, retention purge logic.
	- [x] Fixture loader sync/async + run-once sentinel tests (tests/data/test_fixtures_helper.py)
	- [x] Retention purge soft-delete and hard-delete tests (tests/data/test_retention.py)
	- [x] Erasure workflow steps + audit hook test (tests/data/test_erasure.py)
	- [x] Backup verification basic tests (tests/data/test_backup.py)
	- [x] Repository soft-delete behavior covered (tests/db/test_sql_repository_soft_delete.py)
- [x] Verify: data lifecycle test marker. (pytest -m data_lifecycle)
- [x] Docs: lifecycle & retention policies. (see docs/data-lifecycle.md; linked from README)
 - [x] Implement: easy-setup helpers for migrator/fixtures/retention/erasure wiring. (see data/add.py:add_data_lifecycle)

### 8. SLOs & Ops
- [x] Research: existing metrics/logging instrumentation. (see obs.add.add_observability, obs.metrics.asgi PrometheusMiddleware and http_server_* metrics; logging via app.logging.setup_logging)
- [x] Design: metrics naming & labels; error budget methodology. (ADR-0006 — standardize http_server_* and db_pool_* metrics; primary SLI: success rate and request latency; SLOs per endpoint class with 99.9% success and latency targets; monthly error budget with burn alerts)
- [x] Implement: route instrumentation & dashboard spec artifacts. (route_classifier in add_observability; Grafana dashboard JSON at src/svc_infra/obs/grafana/dashboards/http-overview.json)
- [x] Implement: health/readiness/startup probes. (see api/fastapi/ops/add.py:add_probes)
- [x] Implement: maintenance mode flag & circuit breaker. (see api/fastapi/ops/add.py:add_maintenance_mode, circuit_breaker_dependency)
- [x] Tests: probe behavior, breaker trip/reset. (tests/ops/test_ops_probes_and_breaker.py)
- [x] Verify: ops test marker. (pytest -m ops)
- [x] Docs: SLO definitions & ops playbook. (see docs/ops.md; linked from README)
 - [x] Implement: easy-setup helpers for probes/maintenance-mode/circuit-breaker. (see api/fastapi/ops/add.py)

### 9. DX & Quality Gates
- [x] Research: current CI pipeline steps & gaps. (see dx/add.py::write_ci_workflow and tests/dx/test_dx_helpers.py)
- [x] Design: gating order & required checks. (tests, flake8, mypy, pytest -W error, openapi/problem lint, migrations present check)
- [x] Implement: CI templates (tests, lint, mypy, migration check, SBOM, SAST/DAST stubs). (dx/add.py::write_ci_workflow; dx/cli dx migrations/openapi)
- [x] Implement: OpenAPI generation + lint step. (docs/add.py export + dx openapi check command)
- [~] Implement: Problem+JSON error spec + error code registry + linter. (partial — Problem schema lint implemented; error code registry to follow)
- [x] Implement: changelog automation script. (dx changelog command; see svc_infra/dx/changelog.py)
- [x] Tests: error spec adherence & migration check script. (tests/dx/test_dx_checks.py)
- [x] Verify: CI dry-run locally. (dx ci command prints plan and can run steps)
- [x] Docs: contributing & release process. (docs/contributing.md; linked from README)
 - [x] Implement: easy-setup helper/CLI to scaffold CI, checks, and OpenAPI lint steps. (see dx/add.py)

### 10. Docs & SDKs
- [x] Research: existing OpenAPI & docs endpoints. (see ADR 0007)
- [x] Design: examples strategy & SDK generation pipeline. (ADR 0007)
- [x] Implement: enriched OpenAPI (examples, error samples, tags). (x-codeSamples + Problem examples wired)
- [x] Implement: Redoc + Swagger UI (dark mode toggle). (`?theme=dark`)
- [~] Implement: SDK generation (TS/Python) + publish workflow. (CLI scaffolding: svc-infra sdk ts|py|postman; publish flow TBD)
- [x] Implement: Postman collection + curl quickstart. (CLI subcommand + docs examples)
- [x] Tests: OpenAPI lint, SDK smoke import & sample call. (CLI dry-run + offline smoke tests with mocked subprocess)
- [x] Verify: docs test marker / manual review. (pytest -m docs; sdk tests under -m sdk)
- [x] Docs: Developer quickstart & API usage. (docs/docs-and-sdks.md)
 - [x] Implement: easy-setup helper to mount docs endpoints and run SDK generation. (see api/fastapi/docs/add.py)

---
## Nice-to-have (Fast Follows)

### 11. Billing Primitives
- [x] Research: existing payments adapter capabilities. (no existing payments module; jobs/webhooks usable; SQL scaffolds ready)
- [x] Design: usage metering & aggregation approach. (ADR 0008)
- [ ] Implement: data models & migrations (usage_events, usage_aggregates, plans, plan_entitlements, subscriptions, prices, invoices, invoice_lines).
- [ ] Implement: usage ingestion API (idempotent) + list aggregates.
- [ ] Implement: quota/entitlement enforcement decorator/dependency.
- [ ] Implement: aggregation job + invoice generator job (daily -> monthly cycle) + webhooks.
- [ ] Implement: Stripe adapter skeleton (optional) and sync hooks.
- [ ] Tests: ingestion idempotency, aggregation correctness, invoice totals, quota block, webhook flows.
- [ ] Verify: billing test marker.
- [ ] Docs: billing overview & plan config.

### 12. Admin
- [ ] Research: existing admin endpoints/tools.
- [ ] Design: admin scope & permission alignment.
- [ ] Implement: admin API & impersonation (audit logging).
- [ ] Tests: impersonation logging & role restrictions.
- [ ] Verify: admin test marker.
- [ ] Docs: admin usage & guardrails.

### 13. Feature Flags & Experiments
- [ ] Research: current flags or env toggles.
- [ ] Design: flag storage & evaluation order; experiment bucketing.
- [ ] Implement: flag service + decorator.
- [ ] Implement: experiment allocation helper.
- [ ] Tests: rollout % stability, flag precedence.
- [ ] Verify: flags test marker.
- [ ] Docs: lifecycle & experiment design.

### 14. Internationalization & Time
- [ ] Research: timezone handling & formatting utilities.
- [ ] Design: locale extraction & file structure.
- [ ] Implement: translation pipeline & currency helpers.
- [ ] Tests: formatting & fallback.
- [ ] Verify: i18n test marker.
- [ ] Docs: i18n usage notes.

### 15. Search
- [ ] Research: existing search indices.
- [ ] Design: PG TSV/trigram vs external engine decision.
- [ ] Implement: search abstraction & indexing jobs.
- [ ] Tests: relevance & idempotent indexing.
- [ ] Verify: search test marker.
- [ ] Docs: query examples.

### 16. File & Media
- [ ] Research: existing file handling.
- [ ] Design: signed URL strategy & virus scan integration.
- [ ] Implement: upload/download endpoints & thumbnailer.
- [ ] Tests: signature validity, scan hook, lifecycle transitions.
- [ ] Verify: file test marker.
- [ ] Docs: media lifecycle.

### 17. Email / SMS
- [ ] Research: current emailing utilities.
- [ ] Design: provider abstraction & template layer.
- [ ] Implement: sending API + sandbox mode + bounce tracking.
- [ ] Tests: sandbox suppression, template rendering, rate limits.
- [ ] Verify: comms test marker.
- [ ] Docs: messaging & templates.

### 18. Compliance Posture
- [ ] Research: existing compliance artifacts.
- [ ] Design: SOC2 checklist & access review workflow.
- [ ] Implement: access review CLI & data map docs.
- [ ] Tests: access review script behavior.
- [ ] Verify: compliance test marker.
- [ ] Docs: DPIA template & compliance overview.

---
## Quick Wins (Implement Early)

### 19. Immediate Enhancements
- [ ] Research: confirm absence/presence of each quick win.
- [x] Implement: rate limit middleware. (pluggable store + middleware/dependency added)
- [x] Implement: idempotency dependency. (require_idempotency_key + middleware replay/conflict)
- [x] Implement: JobQueue scaffold. (in-memory queue/scheduler/worker + easy_jobs)
- [ ] Implement: tenant mixin prototype.
- [x] Implement: audit log helper & sinks. (append-only + hash chain; service wrapper)
- [ ] Implement: webhook helper package.
- [x] Implement: security headers middleware.
- [ ] Implement: error code registry + linter.
- [ ] Implement: core CLI commands (admin create, rotate keys, seed, backfill, export tenant, run scheduled).
- [ ] Implement: ops templates (Terraform skeleton, blue/green deploy, backup verification job).
- [ ] Tests: each quick win feature (unit + small integration).
- [ ] Verify: quick wins marker.
- [ ] Docs: quick win usage notes.

---
## Tracking & Ordering
Prioritize Must-have top to bottom. Interleave Quick Wins if they unlock infrastructure (e.g., JobQueue before outbox processing). Each section requires: Research complete → Design approved → Implementation + Tests → Verify → Docs.

## Notes / Decisions Log
(note) Record ADRs for rate limiting backend, job queue selection, tenant isolation model, audit log hashing approach, idempotency storage strategy, webhook retry schedule algorithm.

---
## Global Verification & Finalization
- [ ] Run full `pytest` suite after each major category completion.
- [ ] Re-run flaky markers (x3) to ensure stability.
- [ ] Update this checklist with PR links & skip markers (~) for existing features.
- [ ] Produce release readiness report summarizing completed items.
- [ ] Tag version & generate changelog.

Updated: Enhanced production readiness plan with research/design/tests/verify subtasks.
