# svc-infra Integration Review

## Executive Summary
- `setup_service_api` remains the high-level entry point for API construction. It auto-wires common middleware (request IDs, error handling, idempotency, rate limiting) and OpenAPI customisation so downstream services only supply router packages and metadata. 【F:src/svc_infra/api/fastapi/setup.py†L1-L187】
- Auth, SQL, jobs, cache, and observability still expose single-call helpers (`add_auth_users`, `add_sql_db`/`setup_sql`, `easy_jobs`, `init_cache`, `add_observability`) that hide wiring details while keeping flags and dependency overrides for advanced scenarios. 【F:src/svc_infra/api/fastapi/auth/add.py†L27-L329】【F:src/svc_infra/api/fastapi/db/sql/add.py†L1-L118】【F:src/svc_infra/jobs/easy.py†L1-L28】【F:src/svc_infra/cache/__init__.py†L1-L29】【F:src/svc_infra/obs/add.py†L1-L68】
- Security primitives (lockout, session rotation, RBAC/ABAC, audit chain) are packaged as small composable functions and documented patterns, making them easy to reuse outside FastAPI while still integrating with the default auth routers. 【F:src/svc_infra/security/lockout.py†L1-L96】【F:src/svc_infra/security/session.py†L1-L98】【F:src/svc_infra/security/permissions.py†L1-L148】【F:src/svc_infra/security/audit_service.py†L1-L73】【F:docs/security.md†L1-L96】
- Webhook utilities provide signature verification, a subscription service, and a default router, but they do not yet follow the same add-helper pattern (there is no `add_webhooks(app, ...)` or env-driven persistence wiring). This is the primary deviation from the established DX story. 【F:src/svc_infra/webhooks/fastapi.py†L1-L37】【F:src/svc_infra/webhooks/service.py†L1-L45】【F:src/svc_infra/webhooks/router.py†L1-L55】【F:docs/webhooks.md†L1-L59】

## Detailed Findings

### API bootstrap and middleware
- `setup_service_api` builds a parent app and any versioned child apps, runs the OpenAPI mutation pipeline, registers default routers, and attaches middleware without extra code in downstream projects. 【F:src/svc_infra/api/fastapi/setup.py†L1-L187】
- Scoped docs helpers automatically group endpoints when `add_auth_users` or versioned routers are mounted, so projects get organised API docs with minimal configuration. 【F:src/svc_infra/api/fastapi/auth/add.py†L269-L329】
- Idempotency and optimistic locking remain opt-in via middleware or dependencies with clear docs; defaults are safe for local use and can be swapped for Redis-backed stores. 【F:docs/idempotency.md†L1-L110】

### Authentication and security
- `add_auth_users` continues to be the main integration surface. It mounts routers based on flags, configures session middleware from env, and exposes API-key plus OAuth support as toggles. Projects can override policy objects or provider models if needed, preserving flexibility. 【F:src/svc_infra/api/fastapi/auth/add.py†L27-L329】
- Runtime security helpers (principal resolution, `RequireRoles`, `RequireScopes`, `RequirePermission`, ABAC predicates) make it straightforward to guard routes consistently with the dual routers that enforce doc security defaults. 【F:src/svc_infra/api/fastapi/auth/security.py†L1-L146】【F:src/svc_infra/api/fastapi/dual/protected.py†L1-L74】【F:src/svc_infra/security/permissions.py†L1-L148】
- Low-level primitives (lockout, refresh token rotation, audit chain) remain framework agnostic so other stacks can reuse them. Documentation in `docs/security.md` is aligned with the code and offers wiring recipes. 【F:src/svc_infra/security/lockout.py†L1-L96】【F:src/svc_infra/security/session.py†L1-L98】【F:src/svc_infra/security/audit_service.py†L1-L73】【F:docs/security.md†L1-L96】
- Recommendation: add a security bundle similar to `setup_sql` that can register `SecurityHeadersMiddleware` and strict CORS when FastAPI is not created via `setup_service_api`. 【F:src/svc_infra/security/headers.py†L1-L35】

### Data and jobs
- SQL helpers offer both granular (`add_sql_db`, `add_sql_resources`) and bundled (`setup_sql`) flows. They guard against duplicate setup and generate CRUD schemas when not provided, keeping the quick-start feel while allowing custom services. 【F:src/svc_infra/api/fastapi/db/sql/add.py†L1-L118】
- Jobs expose `easy_jobs()` that switches between memory and Redis based on env, matching the pick-style ergonomics used in logging. Documentation explains scheduler tasks and the CLI runner. 【F:src/svc_infra/jobs/easy.py†L1-L28】【F:docs/jobs.md†L1-L65】
- Cache decorators export both `cache_read` and the friendlier aliases (`cached`, `mutates`) so consumers can adopt them incrementally. 【F:src/svc_infra/cache/__init__.py†L1-L29】

### Observability
- `add_observability` lazily imports instrumentation, respects env flags, and returns a shutdown no-op to keep signature compatibility. It tolerates missing dependencies to avoid burdening projects that do not enable metrics. 【F:src/svc_infra/obs/add.py†L1-L68】
- Grafana and Prometheus templates are packaged separately, but the code path aligns with the simple toggle approach used elsewhere.

### Webhooks and outbox
- Signature utilities (`require_signature`, `verify_any`) and service abstractions (`WebhookService`, `InMemoryWebhookSubscriptions`) follow the composable style, and docs describe usage alongside the shared job and outbox infrastructure. 【F:src/svc_infra/webhooks/fastapi.py†L1-L37】【F:src/svc_infra/webhooks/service.py†L1-L45】【F:docs/webhooks.md†L1-L59】
- Gaps relative to the rest of the repo:
  - Router dependencies always create new in-memory stores, so deployments must override dependencies manually. Providing an `add_webhooks(app, store=..., subs=...)` helper that honours env (for example `REDIS_URL`) would mirror `add_sql_db` and `add_observability`. 【F:src/svc_infra/webhooks/router.py†L1-L55】
  - No convenience function registers the router or scheduler tick automatically; consumers must read docs to wire `make_outbox_tick` and queue processors. A top-level helper such as `setup_webhooks(app, outbox=None, inbox=None)` could bundle router inclusion and scheduler guidance.

### Documentation and DX consistency
- Feature guides (security, jobs, webhooks, idempotency) contain quickstart snippets that mirror the API surface, reinforcing the ease-of-setup story. 【F:docs/security.md†L1-L96】【F:docs/jobs.md†L1-L65】【F:docs/webhooks.md†L1-L59】【F:docs/idempotency.md†L1-L110】
- README remains empty; adding a high-level index pointing to these guides would help teams discover the single-call helpers faster. 【F:README.md†L1-L4】
- Consider adding a matrix listing which environment variables drive each helper (`SQL_URL`, `REDIS_URL`, `METRICS_PATH`, `AUTH_*`) to highlight parity across modules.

## Actionable Suggestions
1. **Webhook setup helper** — provide `add_webhooks` or `setup_webhooks` to mount the router, accept dependency overrides, and optionally wire scheduler tasks. Default to env-driven outbox or inbox selection to match other modules. 【F:src/svc_infra/webhooks/router.py†L1-L55】
2. **Security bundle** — offer a helper that installs `SecurityHeadersMiddleware`, strict CORS, and optional signed-cookie settings for apps that bypass `setup_service_api`. This keeps manual FastAPI apps aligned with the default hardening posture. 【F:src/svc_infra/security/headers.py†L1-L35】
3. **Documentation index** — populate `README.md` with links to the feature guides and highlight key add-style helpers so new projects immediately see the plug-and-play building blocks. 【F:README.md†L1-L4】
4. **Environment reference** — add a doc or table enumerating env vars consumed by helpers (SQL_URL, REDIS_URL, METRICS_PATH, AUTH_*), emphasising how swapping values maintains flexibility across deployments.

Overall, aside from the webhook ergonomics gap and missing README guidance, the codebase maintains the quick-start plus override pattern highlighted in your sample usage while exposing low-level hooks for teams that need deeper control.
