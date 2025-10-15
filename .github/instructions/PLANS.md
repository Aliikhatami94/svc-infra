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
- [x] Tests: password policy + lockout (cooldown escalation).
- [x] Tests: session revocation + RBAC enforcement.
- [x] Tests: breach password rejection & pass cases with stubbed checker.
- [x] Tests: audit log hash-chain integrity (tamper detection). (security.audit + test_audit_log_chain)
- [x] Verify: run security marker tests. (auth + security suites passing as of 2025-10-14)
- [x] Docs: security configuration & examples. (see docs/security.md)

### 2. Rate Limiting & Abuse Protection
- [x] Research: confirm no existing rate limiter. (basic middleware existed; refactored to pluggable store)
- [ ] Design: Redis bucket schema (lua vs atomic), config surface.
- [x] Implement: core token bucket / leaky bucket. (in-memory store abstraction)
- [x] Implement: per-route decorators & global middleware. (middleware + dependency factory)
- [x] Implement: 429 Retry-After logic. (headers in 429 + OpenAPI conventions already present)
- [x] Implement: request size & body parse timeout guard. (size limit middleware; parse timeout TBD)
- [x] Implement: basic bot/DoS heuristic metrics hook. (metrics hooks + middleware emits)
- [x] Tests: bucket depletion/reset, per-route override, Retry-After presence. (tests added)
- [x] Verify: rate limiting test marker. (`-m ratelimit` available; auto-tagged tests)
- [x] Docs: usage & tuning. (see docs/rate-limiting.md)

### 3. Idempotency & Concurrency Controls
- [ ] Research: scan for existing idempotency usage or version columns.
- [ ] Design: idempotency table schema + hashing + TTL cleanup job.
- [ ] Implement: idempotency dependency/middleware storing response envelope.
- [ ] Implement: optimistic locking (version columns) + conflict exception.
- [ ] Implement: transactional outbox table + relay worker skeleton.
- [ ] Implement: inbox pattern (dedupe key, processed_at).
- [ ] Tests: idempotent replay, version conflict detection, outbox dispatch.
- [ ] Verify: concurrency test marker suite.
- [ ] Docs: patterns & pitfalls.

### 4. Background Jobs & Scheduling
- [ ] Research: existing job queue/scheduler utilities.
- [ ] Design: Job schema, retry/backoff strategy, cron config format (YAML/DB).
- [ ] Implement: JobQueue abstraction (Redis) with retry, backoff, DLQ.
- [ ] Implement: cron scheduler loader & execution loop.
- [ ] Implement: outbox processor job.
- [ ] Implement: webhook delivery worker integration.
- [ ] Tests: enqueue/dequeue, retry/backoff, cron triggers, DLQ path.
- [ ] Verify: job test marker.
- [ ] Docs: job authoring guide.

### 5. Webhooks Framework
- [ ] Research: existing webhook verification logic.
- [ ] Design: event schema versioning, signature, retry schedule doc.
- [ ] Implement: producer API & persistence model.
- [ ] Implement: HMAC signing & verification middleware.
- [ ] Implement: retry/backoff logic with tracking fields.
- [ ] Implement: secret rotate & test-fire endpoints.
- [ ] Tests: signature validation, retry escalation, version handling.
- [ ] Verify: webhook test marker.
- [ ] Docs: integration guide.

### 6. Tenancy
- [ ] Research: tenant_id coverage across existing models (list gaps).
- [ ] Design: BaseModelTenant mixin & query filter enforcement strategy.
- [ ] Implement: request dependency for tenant resolution.
- [ ] Implement: per-tenant quotas & rate limit overrides.
- [ ] Implement: export tenant CLI.
- [ ] Tests: tenant isolation (queries, rate limits), export correctness.
- [ ] Verify: tenancy test marker.
- [ ] Docs: isolation strategy (soft vs schema vs dedicated DB).

### 7. Data Lifecycle
- [ ] Research: migrations tooling & soft delete usage.
- [ ] Design: soft delete pattern & retention registry.
- [ ] Implement: migrator CLI (status/apply/rollback/seed).
- [ ] Implement: fixture/reference loader (idempotent).
- [ ] Implement: GDPR erasure workflow (queued + audit entry).
- [ ] Implement: retention purge job.
- [ ] Implement: backup verification (PITR job).
- [ ] Tests: soft delete filter, erasure pipeline, retention purge logic.
- [ ] Verify: data lifecycle test marker.
- [ ] Docs: lifecycle & retention policies.

### 8. SLOs & Ops
- [ ] Research: existing metrics/logging instrumentation.
- [ ] Design: metrics naming & labels; error budget methodology.
- [ ] Implement: route instrumentation & dashboard spec artifacts.
- [ ] Implement: health/readiness/startup probes.
- [ ] Implement: maintenance mode flag & circuit breaker.
- [ ] Tests: probe behavior, breaker trip/reset.
- [ ] Verify: ops test marker.
- [ ] Docs: SLO definitions & ops playbook.

### 9. DX & Quality Gates
- [ ] Research: current CI pipeline steps & gaps.
- [ ] Design: gating order & required checks.
- [ ] Implement: CI templates (tests, lint, mypy, migration check, SBOM, SAST/DAST stubs).
- [ ] Implement: OpenAPI generation + lint step.
- [ ] Implement: Problem+JSON error spec + error code registry + linter.
- [ ] Implement: changelog automation script.
- [ ] Tests: error spec adherence & migration check script.
- [ ] Verify: CI dry-run locally.
- [ ] Docs: contributing & release process.

### 10. Docs & SDKs
- [ ] Research: existing OpenAPI & docs endpoints.
- [ ] Design: examples strategy & SDK generation pipeline.
- [ ] Implement: enriched OpenAPI (examples, error samples, tags).
- [ ] Implement: Redoc + Swagger UI (dark mode toggle).
- [ ] Implement: SDK generation (TS/Python) + publish workflow.
- [ ] Implement: Postman collection + curl quickstart.
- [ ] Tests: OpenAPI lint, SDK smoke import & sample call.
- [ ] Verify: docs test marker / manual review.
- [ ] Docs: Developer quickstart & API usage.

---
## Nice-to-have (Fast Follows)

### 11. Billing Primitives
- [ ] Research: existing payments adapter capabilities.
- [ ] Design: usage metering & aggregation approach.
- [ ] Implement: metering capture & quota enforcement.
- [ ] Implement: Stripe extension (webhooks, proration, invoice PDFs).
- [ ] Tests: aggregation, quota block, webhook flows.
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
- [ ] Implement: rate limit middleware.
- [ ] Implement: idempotency dependency.
- [ ] Implement: JobQueue scaffold.
- [ ] Implement: tenant mixin prototype.
- [ ] Implement: audit log helper & sinks.
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
