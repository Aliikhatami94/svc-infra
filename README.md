<div align="center">

# svc-infra

[![v1.0.0](https://img.shields.io/badge/version-1.0.0-green.svg)](CHANGELOG.md)
[![CI](https://github.com/nfraxlab/svc-infra/actions/workflows/ci.yml/badge.svg)](https://github.com/nfraxlab/svc-infra/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/svc-infra.svg)](https://pypi.org/project/svc-infra/)
[![Python](https://img.shields.io/pypi/pyversions/svc-infra.svg)](https://pypi.org/project/svc-infra/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/svc-infra.svg)](https://pypi.org/project/svc-infra/)
[![codecov](https://codecov.io/gh/nfraxlab/svc-infra/branch/main/graph/badge.svg)](https://codecov.io/gh/nfraxlab/svc-infra)

### Production-ready FastAPI infrastructure in one import

**Stop rebuilding auth, billing, webhooks, and background jobs for every project.**

[Documentation](docs/) · [Examples](examples/) · [PyPI](https://pypi.org/project/svc-infra/) · [Changelog](CHANGELOG.md)

</div>

---

## Why svc-infra?

Every FastAPI project needs the same things: authentication, database setup, background jobs, caching, webhooks, billing... You've written this code before. Multiple times.

**svc-infra** packages battle-tested infrastructure used in production, so you can focus on your actual product:

```python
from svc_infra.api.fastapi.ease import easy_service_app

app = easy_service_app(name="MyAPI", release="1.0.0")
# ✅ Health checks, CORS, security headers, structured logging
# ✅ Prometheus metrics, OpenTelemetry tracing
# ✅ Request IDs, idempotency middleware
# That's it. Ship it.
```

## ⚡ Quick Install

```bash
pip install svc-infra
```

## 🎯 What's Included

| Feature | What You Get | One-liner |
|---------|-------------|-----------|
| **🔐 Auth** | JWT, sessions, OAuth/OIDC, MFA, API keys | `add_auth_users(app)` |
| **💳 Billing** | Usage tracking, subscriptions, invoices, Stripe sync | `add_billing(app)` |
| **📦 Database** | PostgreSQL + MongoDB, migrations, inbox/outbox | `add_sql_db(app)` |
| **⚡ Jobs** | Background tasks, scheduling, retries, DLQ | `easy_jobs()` |
| **🔗 Webhooks** | Subscriptions, HMAC signing, delivery retries | `add_webhooks(app)` |
| **💾 Cache** | Redis/memory, decorators, namespacing | `init_cache()` |
| **📊 Observability** | Prometheus, Grafana dashboards, OTEL | Built-in |
| **📁 Storage** | S3, local, memory backends | `add_storage(app)` |
| **🏢 Multi-tenancy** | Tenant isolation, scoped queries | Built-in |
| **🚦 Rate Limiting** | Per-user, per-endpoint, headers | Built-in |

## 🚀 30-Second Example

Build a complete SaaS backend:

```python
from fastapi import Depends
from svc_infra.api.fastapi.ease import easy_service_app
from svc_infra.api.fastapi.db.sql.add import add_sql_db
from svc_infra.api.fastapi.auth import add_auth_users, current_active_user
from svc_infra.jobs.easy import easy_jobs
from svc_infra.webhooks.fastapi import require_signature

# Create app with batteries included
app = easy_service_app(name="MySaaS", release="1.0.0")

# Add infrastructure
add_sql_db(app)                    # PostgreSQL with migrations
add_auth_users(app)                # Full auth system
queue, scheduler = easy_jobs()     # Background jobs

# Your actual business logic
@app.post("/api/process")
async def process_data(user=Depends(current_active_user)):
    job = queue.enqueue("heavy_task", {"user_id": user.id})
    return {"job_id": job.id, "status": "queued"}

# Webhook endpoint with signature verification
@app.post("/webhooks/stripe")
async def stripe_webhook(payload=Depends(require_signature(lambda: ["whsec_..."]))):
    queue.enqueue("process_payment", payload)
    return {"received": True}
```

**That's a production-ready API** with auth, database, background jobs, and webhook handling.

## 📚 Feature Highlights

### 🔐 Authentication & Security

Full auth system with zero boilerplate:

```python
from svc_infra.api.fastapi.auth import add_auth_users, current_active_user

add_auth_users(app)  # Registers /auth/* routes automatically

@app.get("/me")
async def get_profile(user=Depends(current_active_user)):
    return {"email": user.email, "mfa_enabled": user.mfa_enabled}
```

**Includes:** JWT tokens, session cookies, OAuth/OIDC (Google, GitHub, etc.), MFA/TOTP, password policies, account lockout, key rotation.

### 💳 Usage-Based Billing

Track usage and generate invoices:

```python
from svc_infra.billing import BillingService

billing = BillingService(session=db, tenant_id="tenant_123")

# Record API usage (idempotent)
billing.record_usage(metric="api_calls", amount=1, idempotency_key="req_abc")

# Generate monthly invoice
invoice = billing.generate_monthly_invoice(
    period_start=datetime(2025, 1, 1),
    period_end=datetime(2025, 2, 1),
)
```

**Includes:** Usage events, aggregation, plans & entitlements, subscriptions, invoices, Stripe sync hooks.

### ⚡ Background Jobs

Redis-backed job queue with retries:

```python
from svc_infra.jobs.easy import easy_jobs

queue, scheduler = easy_jobs()  # Auto-detects Redis or uses memory

# Enqueue work
queue.enqueue("send_email", {"to": "user@example.com", "template": "welcome"})

# Schedule recurring tasks
scheduler.add("cleanup", interval_seconds=3600, target="myapp.tasks:cleanup")
```

```bash
# Run the worker
svc-infra jobs run
```

**Includes:** Visibility timeout, exponential backoff, dead letter queue, interval scheduler, CLI worker.

### 🔗 Webhooks

Send and receive webhooks with proper security:

```python
from svc_infra.webhooks import add_webhooks, WebhookService

add_webhooks(app)  # Adds subscription management routes

# Publish events
webhook_service.publish("invoice.paid", {"invoice_id": "inv_123"})

# Verify incoming webhooks
@app.post("/webhooks/external")
async def receive(payload=Depends(require_signature(lambda: ["secret1", "secret2"]))):
    return {"ok": True}
```

**Includes:** Subscription store, HMAC-SHA256 signing, delivery retries, idempotent processing.

### 📊 Observability

Production monitoring out of the box:

```python
app = easy_service_app(name="MyAPI", release="1.0.0")
# Prometheus metrics at /metrics
# Health checks at /healthz, /readyz, /startupz
# Request tracing with OpenTelemetry
```

```bash
# Generate Grafana dashboards
svc-infra obs dashboard --service myapi --output ./dashboards/
```

**Includes:** Prometheus metrics, Grafana dashboard generator, OTEL integration, SLO helpers.

## ⚙️ Configuration

Everything is configurable via environment variables:

```bash
# Database
SQL_URL=postgresql://user:pass@localhost/mydb
MONGO_URL=mongodb://localhost:27017

# Auth
AUTH_JWT__SECRET=your-secret-key
AUTH_SMTP_HOST=smtp.sendgrid.net

# Jobs
JOBS_DRIVER=redis
REDIS_URL=redis://localhost:6379

# Storage
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=my-uploads

# Observability
ENABLE_OBS=true
METRICS_PATH=/metrics
```

See the [Environment Reference](docs/environment.md) for all options.

## 📖 Documentation

| Module | Description | Guide |
|--------|-------------|-------|
| **API** | FastAPI bootstrap, middleware, versioning | [docs/api.md](docs/api.md) |
| **Auth** | Sessions, OAuth/OIDC, MFA, API keys | [docs/auth.md](docs/auth.md) |
| **Billing** | Usage tracking, subscriptions, invoices | [docs/billing.md](docs/billing.md) |
| **Database** | SQL + MongoDB, migrations, patterns | [docs/database.md](docs/database.md) |
| **Jobs** | Background tasks, scheduling | [docs/jobs.md](docs/jobs.md) |
| **Webhooks** | Publishing, signing, verification | [docs/webhooks.md](docs/webhooks.md) |
| **Cache** | Redis/memory caching, TTL helpers | [docs/cache.md](docs/cache.md) |
| **Storage** | S3, local, memory file storage | [docs/storage.md](docs/storage.md) |
| **Observability** | Metrics, tracing, dashboards | [docs/observability.md](docs/observability.md) |
| **Security** | Password policy, headers, MFA | [docs/security.md](docs/security.md) |
| **Tenancy** | Multi-tenant isolation | [docs/tenancy.md](docs/tenancy.md) |
| **CLI** | Command-line tools | [docs/cli.md](docs/cli.md) |

## 🏃 Running the Example

See all features working together:

```bash
git clone https://github.com/nfraxlab/svc-infra.git
cd svc-infra

# Setup and run
make setup-template    # Creates DB, runs migrations
make run-template      # Starts at http://localhost:8001
```

Visit http://localhost:8001/docs to explore the API.

## 🤝 Related Packages

svc-infra is part of the **nfrax** infrastructure suite:

| Package | Purpose |
|---------|---------|
| **[svc-infra](https://github.com/nfraxlab/svc-infra)** | Backend infrastructure (auth, billing, jobs, webhooks) |
| **[ai-infra](https://github.com/nfraxlab/ai-infra)** | AI/LLM infrastructure (agents, tools, RAG, MCP) |
| **[fin-infra](https://github.com/nfraxlab/fin-infra)** | Financial infrastructure (banking, portfolio, insights) |

## 📄 License

MIT License - use it for anything.

---

<div align="center">

**Built with ❤️ by [nfraxlab](https://github.com/nfraxlab)**

[⭐ Star us on GitHub](https://github.com/nfraxlab/svc-infra) · [📦 View on PyPI](https://pypi.org/project/svc-infra/)

</div>
