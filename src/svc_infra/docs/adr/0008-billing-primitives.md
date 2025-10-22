# ADR 0008: Billing Primitives (Usage, Quotas, Invoicing)

## Status

Proposed — Research and Design complete for v1 scope.

## Context

We need shared billing primitives to support both usage-based and subscription features across services. Goals:
- Capture fine-grained usage events with idempotency and tenant isolation.
- Aggregate usage into billable buckets (hour/day/month) with rollups.
- Enforce entitlements/quotas at runtime (hard/soft limits).
- Produce invoice data structures and events; enable later integration with external providers (Stripe, Paddle) without coupling core DX to any vendor.

Non-goals for v1: taxes/VAT, complex proration rules, refunds/credits automation, dunning flows, provider-specific webhooks/end-to-end reconciliation.

## Analysis: APF Payments vs Billing Primitives

What APF Payments already covers (provider-facing):
- Subscriptions lifecycle via provider adapters and HTTP router
  - Endpoints: create/update/cancel/get/list under `/payments/subscriptions` (see `api/fastapi/apf_payments/router.py`).
  - Local mirror rows (e.g., `PaySubscription`) are persisted for reference, but state is owned by the provider (Stripe/Aiydan).
- Plans as Product + Price on the provider side
  - APF Payments exposes products (`/payments/products`) and prices (`/payments/prices`). In Stripe semantics, a “plan” is represented by a product+price pair.
  - There is no first-class internal Plan entity in APF Payments; plan semantics are encapsulated as provider product/price metadata.
- Invoices, invoice line items, and previews
  - Create/finalize/void/pay invoices; add/list invoice lines; preview invoices — all via provider adapters.
- Usage records (metered billing) at the provider
  - Create/list/get usage records mapped to provider subscription items or prices (`/payments/usage_records`).
- Cross-cutting:
  - Tenant resolution, pagination, idempotency, and Problem+JSON errors are integrated.

What APF Payments does not cover (gaps filled by Billing Primitives):
- An internal, provider-agnostic Plan and Entitlement registry (keys, windows, limits).
- Quota enforcement at runtime (soft/hard limits) against internal entitlements.
- Internal usage ingestion and aggregation store independent of provider APIs
  - `UsageEvent` and `UsageAggregate` tables, with idempotent ingestion and windowed rollups.
- Internal invoice modeling and generation from aggregates (not just provider invoices)
  - `Invoice` and `InvoiceLine` entities produced from internal totals (jobs-based lifecycle).
- A dedicated `/_billing` router for usage ingestion and aggregate reads (tenant-scoped, RBAC-protected).

Where they intersect and can complement each other:
- You can continue to use APF Payments for provider-side subscriptions/invoices and also use Billing Primitives to meter internal features and enforce quotas.
- Optional bridging: a provider sync hook can map internally generated invoices/lines to provider invoices or payment intents when you want unified billing.
- Usage: internal `UsageEvent` can be mirrored to provider usage-records if desired, but internal aggregation enables analytics and quota decisions without provider round-trips.

Answering “Are plans and subscriptions covered in APF Payments?”
- Subscriptions: Yes — fully supported via `/payments/subscriptions` endpoints with adapters (Stripe/Aiydan). APF also persists a local `PaySubscription` record for reference.
- Plans: APF Payments does not expose a standalone internal Plan model. Instead, providers represent plans as Product + Price. Billing Primitives introduces an internal `Plan` and `PlanEntitlement` registry to support provider-agnostic limits and quotas.

## Decisions

1) Internal-first data model with optional provider adapters
- Persist usage, aggregates, plans, subscriptions, invoices in our SQL layer.
- Provide interfaces for provider adapters (Stripe later) to map internal invoices/lines and sync state when enabled.

2) Usage ingestion API + idempotency
- FastAPI router exposes POST /_billing/usage capturing events: {tenant_id, metric, amount, at, idempotency_key, metadata}.
- Enforce request idempotency via existing middleware + usage-event unique index on (tenant_id, metric, idempotency_key).
- Emit webhook event `billing.usage_recorded` (optional).

3) Aggregation job (scheduler)
- Background job reads new UsageEvent rows, aggregates into UsageAggregate by key (tenant, metric, period_start, period_granularity).
- Granularities: hour, day, month (config). Maintains running totals; idempotent.
- Emits `billing.usage_aggregated` webhook.

4) Entitlements and quotas
- Define Plan and PlanEntitlement models (feature flags, quotas per window).
- Subscriptions bind tenant -> plan, effective_at/ended_at.
- Runtime enforcement via dependency/decorator: `require_quota("metric", window="day", soft=True)` which raises/records when limit exceeded.

5) Invoicing primitives
- Invoice and InvoiceLine models created for each billing cycle (monthly default). Lines derived from aggregates and static prices.
- Price model: unit amount, currency, metric reference (for metered), or fixed recurring.
- Emit `billing.invoice_created` and `billing.invoice_finalized` webhooks; provider adapter can consume and sync out.

6) Observability
- Metrics: `billing_usage_ingest_total`, `billing_aggregate_duration_ms`, `billing_invoice_generated_total`.
- Logs: aggregation windows processed, invoice cycles.

7) Security & tenancy
- All models include tenant_id; APIs require tenant context. RBAC: billing.read/billing.write for admin/operator roles.

## Data Model (SQL)

Tables (minimal v1):
- usage_events(id, tenant_id, metric, amount, at_ts, idempotency_key, metadata_json, created_at)
  - Unique (tenant_id, metric, idempotency_key)
- usage_aggregates(id, tenant_id, metric, period_start, granularity, total, updated_at)
  - Unique (tenant_id, metric, period_start, granularity)
- plans(id, key, name, description, created_at)
- plan_entitlements(id, plan_id, key, limit_per_window, window, created_at)
- subscriptions(id, tenant_id, plan_id, effective_at, ended_at, created_at)
- prices(id, key, currency, unit_amount, metric, recurring_interval, created_at)
- invoices(id, tenant_id, period_start, period_end, status, total_amount, currency, created_at)
- invoice_lines(id, invoice_id, price_id, metric, quantity, amount, created_at)

All tables will be scaffolded with our SQL helpers and tenant mixin, with Alembic templates.

## APIs

- POST /_billing/usage: record usage events (body as above). Returns 202 with event id.
- GET /_billing/usage: list usage by metric and window (aggregated).
- GET /_billing/plans, GET /_billing/subscriptions, POST /_billing/subscriptions.
- GET /_billing/invoices, GET /_billing/invoices/{id}.

Routers mounted under a `/_billing` prefix and hidden behind auth + tenant guard. OpenAPI tags: Billing.

## Jobs & Webhooks

- Job: `aggregate_usage` runs on schedule; creates/updates UsageAggregate rows.
- Job: `generate_invoices` runs monthly; emits invoice events and inserts Invoice/InvoiceLine rows.
- Webhooks: `billing.usage_recorded`, `billing.usage_aggregated`, `billing.invoice_created`, `billing.invoice_finalized` (signed via existing module).

## Implementation Plan (Phased)

Phase 1 (MVP):
- Models + migrations; CRUD for Plans/Subs/Prices; Usage ingestion + idempotency; Aggregator job (daily granularity); Basic invoice generator (monthly, fixed price + metered by day sum); Webhooks emitted; Tests for ingestion, aggregation, simple invoice.

Phase 2:
- Granularity options (hourly); soft/hard quota decorator; Read APIs; Observability metrics; Docs.

Phase 3 (Provider adapter optional):
- Stripe adapter skeleton: map internal invoices/lines -> Stripe, idempotent sync; basic webhook handler to update statuses.

## Alternatives Considered

- Provider-first approach (Stripe-only) rejected for v1 to keep core DX portable and support non-card use-cases.
- Event-stream aggregation (Kafka) out-of-scope for framework baseline—can be integrated later.

## Risks

- Complexity creep around proration and taxes—explicitly out-of-scope for v1.
- Performance on large tenants—mitigated by granular aggregation and indexes.

## Testing

- Unit tests for ingestion idempotency, aggregation correctness, invoice totals.
- E2E-ish tests using in-memory queue + sqlite.

## Documentation

- `docs/billing.md`: usage API, quotas, invoice lifecycle, and Stripe adapter notes.
