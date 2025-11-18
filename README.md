# svc-infra

[![PyPI](https://img.shields.io/pypi/v/svc-infra.svg)](https://pypi.org/project/svc-infra/)
[![Docs](https://img.shields.io/badge/docs-reference-blue)](.)

svc-infra packages the shared building blocks we use to ship production FastAPI services fast—HTTP APIs with secure auth, durable persistence, background execution, cache, observability, and webhook plumbing that all share the same batteries-included defaults.

## Helper index

| Area | What it covers | Guide |
| --- | --- | --- |
| Getting Started | Overview and entry points | [This page](src/svc_infra/docs/getting-started.md) |
| Environment | Feature switches and env vars | [Environment](src/svc_infra/docs/environment.md) |
| API | FastAPI bootstrap, middleware, docs wiring | [API guide](src/svc_infra/docs/api.md) |
| Auth | Sessions, OAuth/OIDC, MFA, SMTP delivery | [Auth](src/svc_infra/docs/auth.md) |
| Security | Password policy, lockout, signed cookies, headers | [Security](src/svc_infra/docs/security.md) |
| Database | SQL + Mongo wiring, Alembic helpers, inbox/outbox patterns | [Database](src/svc_infra/docs/database.md) |
| Storage | File storage with S3, local, memory backends | [Storage](src/svc_infra/docs/storage.md) |
| Documents | Generic document management with metadata | [Documents](src/svc_infra/docs/documents.md) |
| Tenancy | Multi-tenant boundaries and helpers | [Tenancy](src/svc_infra/docs/tenancy.md) |
| Idempotency | Idempotent endpoints and middleware | [Idempotency](src/svc_infra/docs/idempotency.md) |
| Rate Limiting | Middleware, dependency limiter, headers | [Rate limiting](src/svc_infra/docs/rate-limiting.md) |
| Cache | cashews decorators, namespace management, TTL helpers | [Cache](src/svc_infra/docs/cache.md) |
| Jobs | JobQueue, scheduler, CLI worker | [Jobs](src/svc_infra/docs/jobs.md) |
| Observability | Prometheus, Grafana, OpenTelemetry | [Observability](src/svc_infra/docs/observability.md) |
| Ops | Probes, breakers, SLOs & dashboards | [Ops](src/svc_infra/docs/ops.md) |
| Webhooks | Subscription store, signing, retry worker | [Webhooks](src/svc_infra/docs/webhooks.md) |
| CLI | Command groups for sql/mongo/obs/docs/dx/sdk/jobs | [CLI](src/svc_infra/docs/cli.md) |
| Docs & SDKs | Publishing docs, generating SDKs | [Docs & SDKs](src/svc_infra/docs/docs-and-sdks.md) |
| Acceptance | Acceptance harness and flows | [Acceptance](src/svc_infra/docs/acceptance.md), [Matrix](src/svc_infra/docs/acceptance-matrix.md) |
| Contributing | Dev setup and quality gates | [Contributing](src/svc_infra/docs/contributing.md) |
| Repo Review | Checklist for releasing/PRs | [Repo review](src/svc_infra/docs/repo-review.md) |
| Data Lifecycle | Fixtures, retention, erasure, backups | [Data lifecycle](src/svc_infra/docs/data-lifecycle.md) |

## Quick Start with Template Example

See **ALL** svc-infra features working together in a complete example:

```bash
# One-time setup (from repo root)
make setup-template    # Scaffolds models, runs migrations

# Run the example server
make run-template      # Starts at http://localhost:8001
```

See [`examples/README.md`](examples/README.md) for full documentation and manual setup options.

## Minimal FastAPI bootstrap

```python
from fastapi import Depends
from svc_infra.api.fastapi.ease import easy_service_app
from svc_infra.api.fastapi.db.sql.add import add_sql_db
from svc_infra.cache import init_cache
from svc_infra.jobs.easy import easy_jobs
from svc_infra.webhooks.fastapi import require_signature

app = easy_service_app(name="Billing", release="1.2.3")
add_sql_db(app)              # reads SQL_URL / DB_* envs
init_cache()                 # honors CACHE_PREFIX / CACHE_VERSION
queue, scheduler = easy_jobs()  # switches via JOBS_DRIVER / REDIS_URL

@app.post("/webhooks/billing")
async def handle_webhook(payload = Depends(require_signature(lambda: ["current", "next"]))):
    queue.enqueue("process-billing-webhook", payload)
    return {"status": "queued"}
```

## Environment switches

- **API** – toggle logging/observability and docs exposure with `ENABLE_LOGGING`, `LOG_LEVEL`, `LOG_FORMAT`, `ENABLE_OBS`, `METRICS_PATH`, `OBS_SKIP_PATHS`, and `CORS_ALLOW_ORIGINS`. 【F:src/svc_infra/api/fastapi/ease.py†L67-L111】【F:src/svc_infra/api/fastapi/setup.py†L47-L88】
- **Auth** – configure JWT secrets, SMTP, cookies, and policy using the `AUTH_…` settings family (e.g., `AUTH_JWT__SECRET`, `AUTH_SMTP_HOST`, `AUTH_SESSION_COOKIE_SECURE`). 【F:src/svc_infra/api/fastapi/auth/settings.py†L23-L91】
- **Database** – set connection URLs or components via `SQL_URL`/`SQL_URL_FILE`, `DB_DIALECT`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, plus Mongo knobs like `MONGO_URL`, `MONGO_DB`, and `MONGO_URL_FILE`. 【F:src/svc_infra/api/fastapi/db/sql/add.py†L55-L114】【F:src/svc_infra/db/sql/utils.py†L85-L206】【F:src/svc_infra/db/nosql/mongo/settings.py†L9-L13】【F:src/svc_infra/db/nosql/utils.py†L56-L113】
- **Storage** – choose backend with `STORAGE_BACKEND` (local, s3, memory) and configure with `STORAGE_S3_BUCKET`, `STORAGE_S3_REGION`, `STORAGE_BASE_PATH`, or auto-detect from `RAILWAY_VOLUME_MOUNT_PATH` / AWS credentials. 【F:src/svc_infra/storage/settings.py】【F:src/svc_infra/docs/storage.md】
- **Jobs** – choose the queue backend with `JOBS_DRIVER` and provide Redis via `REDIS_URL`; interval schedules can be declared with `JOBS_SCHEDULE_JSON`. 【F:src/svc_infra/jobs/easy.py†L11-L27】【F:src/svc_infra/docs/jobs.md†L11-L48】
- **Cache** – namespace keys and lifetimes through `CACHE_PREFIX`, `CACHE_VERSION`, and TTL overrides `CACHE_TTL_DEFAULT`, `CACHE_TTL_SHORT`, `CACHE_TTL_LONG`. 【F:src/svc_infra/cache/README.md†L20-L173】【F:src/svc_infra/cache/ttl.py†L26-L55】
- **Observability** – turn metrics on/off or adjust scrape paths with `ENABLE_OBS`, `METRICS_PATH`, `OBS_SKIP_PATHS`, and Prometheus/Grafana flags like `SVC_INFRA_DISABLE_PROMETHEUS`, `SVC_INFRA_RATE_WINDOW`, `SVC_INFRA_DASHBOARD_REFRESH`, `SVC_INFRA_DASHBOARD_RANGE`. 【F:src/svc_infra/api/fastapi/ease.py†L67-L111】【F:src/svc_infra/obs/metrics/asgi.py†L49-L206】【F:src/svc_infra/obs/cloud_dash.py†L85-L108】
- **Webhooks** – reuse the jobs envs (`JOBS_DRIVER`, `REDIS_URL`) for the delivery worker and queue configuration. 【F:src/svc_infra/docs/webhooks.md†L32-L53】
- **Security** – enforce password policy, MFA, and rotation with auth prefixes such as `AUTH_PASSWORD_MIN_LENGTH`, `AUTH_PASSWORD_REQUIRE_SYMBOL`, `AUTH_JWT__SECRET`, and `AUTH_JWT__OLD_SECRETS`. 【F:src/svc_infra/docs/security.md†L24-L70】
