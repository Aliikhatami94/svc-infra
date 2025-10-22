# Billing Primitives

This module provides internal-first billing building blocks for services that need usage-based and subscription billing without coupling to a specific provider. It complements APF Payments (provider-facing) with portable primitives you can use regardless of Stripe/Aiydan/etc.

## What you get

- Usage ingestion with idempotency (UsageEvent)
- Windowed usage aggregation (UsageAggregate) — daily baseline
- Plan and entitlements registry (Plan, PlanEntitlement)
- Tenant subscriptions (Subscription)
- Price catalog for fixed/usage items (Price)
- Invoice and line items (Invoice, InvoiceLine)
- A small `BillingService` to record usage, aggregate, and generate monthly invoices
- Optional provider sync hook to mirror internal invoices/lines to your payment provider

## Data model (SQL)

Tables (v1):
- usage_events(id, tenant_id, metric, amount, at_ts, idempotency_key, metadata_json, created_at)
  - Unique (tenant_id, metric, idempotency_key)
- usage_aggregates(id, tenant_id, metric, period_start, granularity, total, updated_at)
  - Unique (tenant_id, metric, period_start, granularity)
- plans(id, key, name, description, created_at)
- plan_entitlements(id, plan_id, key, limit_per_window, window, created_at)
- subscriptions(id, tenant_id, plan_id, effective_at, ended_at, created_at)
- prices(id, key, currency, unit_amount, metric, recurring_interval, created_at)
- invoices(id, tenant_id, period_start, period_end, status, total_amount, currency, provider_invoice_id, created_at)
- invoice_lines(id, invoice_id, price_id, metric, quantity, amount, created_at)

See `src/svc_infra/billing/models.py` for full definitions.

## Quick start (Python)

```python
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from svc_infra.billing import BillingService

# session: SQLAlchemy Session (sync) targeting your DB
bs = BillingService(session=session, tenant_id="t_123")

# 1) Record usage (idempotent by (tenant, metric, idempotency_key))
evt_id = bs.record_usage(
    metric="tokens", amount=42,
    at=datetime.now(tz=timezone.utc),
    idempotency_key="req-42",
    metadata={"model": "gpt"},
)

# 2) Aggregate for a day (baseline v1 granularity)
bs.aggregate_daily(metric="tokens", day_start=datetime(2025,1,1,tzinfo=timezone.utc))

# 3) Generate a monthly invoice (fixed+usage lines TBD)
inv_id = bs.generate_monthly_invoice(
    period_start=datetime(2025,1,1,tzinfo=timezone.utc),
    period_end=datetime(2025,2,1,tzinfo=timezone.utc),
    currency="usd",
)
```

Optional: pass a provider sync hook if you want to mirror invoices/lines to Stripe/Aiydan:

```python
from typing import Callable
from svc_infra.billing.models import Invoice, InvoiceLine

async def sync_to_provider(inv: Invoice, lines: list[InvoiceLine]):
    # Map internal invoice/lines to provider calls here
    ...

bs = BillingService(session=session, tenant_id="t_123", provider_sync=sync_to_provider)
```

### FastAPI router (usage ingestion & aggregates)

Mount the router and start recording usage with idempotency:

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.billing.setup import add_billing
from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware
from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers

app = FastAPI()
app.add_middleware(IdempotencyMiddleware, store={})
register_error_handlers(app)
add_billing(app)  # mounts under /_billing

# POST /_billing/usage  {metric, amount, at?, idempotency_key, metadata?} -> 202 {id}
# GET  /_billing/usage?metric=tokens -> {items: [{period_start, granularity, metric, total}], next_cursor}
```

### Quotas (soft/hard limits)

Protect your feature endpoints with a quota dependency based on internal plan entitlements and daily aggregates:

```python
from fastapi import Depends
from svc_infra.billing.quotas import require_quota

@app.get("/generate-report", dependencies=[Depends(require_quota("reports", window="day", soft=False))])
async def generate_report():
  return {"ok": True}
```

## Relationship to APF Payments

- APF Payments is provider-facing: customers, intents, methods, products/prices, subscriptions, invoices, usage records via Stripe/Aiydan adapters and HTTP routers.
- Billing Primitives is provider-agnostic: an internal ledger of usage, plans/entitlements, and invoices that you can keep even if you change providers.
- You can use both: continue to use APF Payments for card/payments flows, and use Billing to meter custom features and create internal invoices; selectively sync them out later.

## Jobs and webhooks

Billing includes helpers to enqueue and process jobs and emit webhooks:

- Job names:
  - `billing.aggregate_daily` payload: `{tenant_id, metric, day_start: ISO8601}`
  - `billing.generate_monthly_invoice` payload: `{tenant_id, period_start: ISO8601, period_end: ISO8601, currency}`
- Emitted webhook topics:
  - `billing.usage_aggregated` payload: `{tenant_id, metric, day_start, total}`
  - `billing.invoice.created` payload: `{tenant_id, invoice_id, period_start, period_end, currency}`

Usage with the built-in queue/scheduler and webhooks outbox:

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from svc_infra.jobs.easy import easy_jobs
from svc_infra.webhooks.add import add_webhooks
from svc_infra.webhooks.service import WebhookService
from svc_infra.db.outbox import InMemoryOutboxStore
from svc_infra.webhooks.service import InMemoryWebhookSubscriptions
from svc_infra.billing.jobs import (
    enqueue_aggregate_daily,
    enqueue_generate_monthly_invoice,
    make_billing_job_handler,
)

# Create queue + scheduler
queue, scheduler = easy_jobs()

# Setup DB async session factory
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Setup webhooks (in-memory stores shown here)
outbox = InMemoryOutboxStore()
subs = InMemoryWebhookSubscriptions()
subs.add("billing.usage_aggregated", url="https://example.test/hook", secret="sekrit")
webhooks = WebhookService(outbox=outbox, subs=subs)

# Worker handler
handler = make_billing_job_handler(session_factory=SessionLocal, webhooks=webhooks)

# Enqueue example jobs
from datetime import datetime, timezone
enqueue_aggregate_daily(queue, tenant_id="t1", metric="tokens", day_start=datetime.now(timezone.utc))
enqueue_generate_monthly_invoice(
    queue, tenant_id="t1", period_start=datetime(2025,1,1,tzinfo=timezone.utc), period_end=datetime(2025,2,1,tzinfo=timezone.utc), currency="usd"
)

# In your worker loop call process_one(queue, handler)
```

## Roadmap (v1 scope)

- Router: `/_billing` endpoints for usage ingestion (idempotent), aggregate listing, plans/subscriptions read.
- Quotas: decorator/dependency to enforce per-plan limits (soft/hard, day/month windows).
- Jobs: integrate aggregation and invoice-generation with the scheduler; emit `billing.*` webhooks. (helpers available in `svc_infra.billing.jobs`) — Implemented.
- Provider sync: optional mapper to Stripe invoices/payment intents; reuse idempotency.
- Migrations: author initial Alembic migration for billing tables.
- Docs: examples for quotas and jobs; admin flows for plans and prices.

## Testing

- See `tests/unit/billing/test_billing_service.py` for usage, aggregation, invoice basics, and idempotency uniqueness.
- Additions planned: router tests (ingest/list), quotas, job executions, webhook events.

## Security & Tenancy

- All records are tenant-scoped; ensure tenant_id is enforced in your service layer / router dependencies.
- Protect HTTP endpoints with RBAC permissions (e.g., billing.read, billing.write) if you expose them.

## Observability

Planned metrics (names may evolve):
- billing_usage_ingest_total
- billing_aggregate_duration_ms
- billing_invoice_generated_total

See ADR 0008 for design details.
