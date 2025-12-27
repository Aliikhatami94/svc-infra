# Usage-Based Billing

svc-infra provides primitives for usage-based billing: tracking usage events, aggregating
metrics, generating invoices, enforcing quotas, and syncing with payment providers.

> **Note**: svc-infra handles usage tracking and invoice generation. For payment processing,
> see [fin-infra APF Payments](https://fin-infra.nfrax.com/payments) which handles Stripe
> integration, payment methods, and financial compliance.

---

## Quick Start

```python
from datetime import datetime, timezone
from svc_infra.billing import AsyncBillingService

async with async_session_maker() as session:
    billing = AsyncBillingService(session, tenant_id="tenant_123")

    # Record usage event
    event_id = await billing.record_usage(
        metric="api_calls",
        amount=1,
        at=datetime.now(timezone.utc),
        idempotency_key="req-abc123",
        metadata={"endpoint": "/api/v1/users", "method": "GET"},
    )

    await session.commit()
```

---

## Data Model

### Core Entities

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   UsageEvent    │     │  UsageAggregate  │     │     Invoice     │
├─────────────────┤     ├──────────────────┤     ├─────────────────┤
│ id              │     │ id               │     │ id              │
│ tenant_id       │────▶│ tenant_id        │────▶│ tenant_id       │
│ metric          │     │ metric           │     │ period_start    │
│ amount          │     │ period_start     │     │ period_end      │
│ at_ts           │     │ granularity      │     │ status          │
│ idempotency_key │     │ total            │     │ total_amount    │
│ metadata_json   │     └──────────────────┘     │ currency        │
└─────────────────┘                              │ provider_id     │
                                                 └─────────────────┘
                                                         │
                                                         ▼
                                                 ┌─────────────────┐
                                                 │   InvoiceLine   │
                                                 ├─────────────────┤
                                                 │ id              │
                                                 │ invoice_id      │
                                                 │ price_id        │
                                                 │ metric          │
                                                 │ quantity        │
                                                 │ amount          │
                                                 └─────────────────┘
```

### Plans and Subscriptions

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│      Plan       │     │ PlanEntitlement  │     │  Subscription   │
├─────────────────┤     ├──────────────────┤     ├─────────────────┤
│ id              │────▶│ id               │     │ id              │
│ name            │     │ plan_id          │     │ tenant_id       │
│ description     │     │ metric           │     │ plan_id         │──▶ Plan
│ interval        │     │ included_amount  │     │ status          │
│ currency        │     │ overage_unit_price│    │ current_period_s│
│ base_price      │     └──────────────────┘     │ current_period_e│
│ provider_id     │                              │ cancel_at_period│
└─────────────────┘                              └─────────────────┘

┌─────────────────┐
│      Price      │
├─────────────────┤
│ id              │
│ plan_id         │──▶ Plan
│ metric          │
│ unit_amount     │
│ currency        │
│ tiers           │ (JSON for tiered pricing)
│ provider_id     │
└─────────────────┘
```

---

## AsyncBillingService

The primary API for billing operations. Always use the async version for new code.

### Recording Usage

```python
from datetime import datetime, timezone
from svc_infra.billing import AsyncBillingService

async def track_api_call(
    session: AsyncSession,
    tenant_id: str,
    endpoint: str,
    method: str,
    request_id: str,
):
    billing = AsyncBillingService(session, tenant_id)

    await billing.record_usage(
        metric="api_calls",
        amount=1,
        at=datetime.now(timezone.utc),
        idempotency_key=request_id,  # Prevents double-counting
        metadata={
            "endpoint": endpoint,
            "method": method,
        },
    )
```

**Best practices:**

- Always use UTC timestamps
- Use unique `idempotency_key` per event to prevent duplicates
- Include relevant context in metadata for debugging

### Aggregating Usage

Daily aggregation rolls up events into summaries:

```python
from datetime import datetime, timezone, timedelta

async def run_daily_aggregation(session: AsyncSession, tenant_id: str):
    billing = AsyncBillingService(session, tenant_id)

    # Aggregate yesterday's usage
    yesterday = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)

    for metric in ["api_calls", "storage_gb", "compute_minutes"]:
        total = await billing.aggregate_daily(
            metric=metric,
            day_start=yesterday,
        )
        print(f"{metric}: {total} on {yesterday.date()}")
```

### Querying Aggregates

```python
async def get_usage_report(
    session: AsyncSession,
    tenant_id: str,
    metric: str,
    start_date: datetime,
    end_date: datetime,
) -> list[UsageAggregate]:
    billing = AsyncBillingService(session, tenant_id)

    return await billing.list_daily_aggregates(
        metric=metric,
        date_from=start_date,
        date_to=end_date,
    )
```

### Generating Invoices

```python
from datetime import datetime, timezone
from calendar import monthrange

async def generate_monthly_invoice(session: AsyncSession, tenant_id: str):
    billing = AsyncBillingService(session, tenant_id)

    # Calculate billing period
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = monthrange(now.year, now.month)[1]
    period_end = period_start.replace(day=last_day) + timedelta(days=1)

    invoice_id = await billing.generate_monthly_invoice(
        period_start=period_start,
        period_end=period_end,
        currency="usd",
    )

    return invoice_id
```

---

## FastAPI Integration

### Billing Router

```python
from fastapi import APIRouter, Depends
from svc_infra.billing import AsyncBillingService
from svc_infra.api.fastapi import require_auth

router = APIRouter(prefix="/billing", tags=["billing"])

@router.post("/usage")
async def record_usage(
    metric: str,
    amount: int,
    user = Depends(require_auth),
    session = Depends(get_async_session),
):
    billing = AsyncBillingService(session, user.tenant_id)

    event_id = await billing.record_usage(
        metric=metric,
        amount=amount,
        at=datetime.now(timezone.utc),
        idempotency_key=str(uuid.uuid4()),
        metadata={"user_id": user.id},
    )

    await session.commit()
    return {"event_id": event_id}

@router.get("/usage")
async def get_usage(
    metric: str,
    start_date: datetime,
    end_date: datetime,
    user = Depends(require_auth),
    session = Depends(get_async_session),
):
    billing = AsyncBillingService(session, user.tenant_id)

    aggregates = await billing.list_daily_aggregates(
        metric=metric,
        date_from=start_date,
        date_to=end_date,
    )

    return {
        "metric": metric,
        "period": {"start": start_date, "end": end_date},
        "data": [
            {"date": a.period_start.date(), "total": a.total}
            for a in aggregates
        ],
    }

@router.get("/invoices")
async def list_invoices(
    user = Depends(require_auth),
    session = Depends(get_async_session),
):
    result = await session.execute(
        select(Invoice)
        .where(Invoice.tenant_id == user.tenant_id)
        .order_by(Invoice.period_start.desc())
    )
    return result.scalars().all()
```

### Middleware for Automatic Tracking

```python
from starlette.middleware.base import BaseHTTPMiddleware

class UsageTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Track API calls for authenticated requests
        if hasattr(request.state, "user"):
            async with async_session_maker() as session:
                billing = AsyncBillingService(session, request.state.user.tenant_id)
                await billing.record_usage(
                    metric="api_calls",
                    amount=1,
                    at=datetime.now(timezone.utc),
                    idempotency_key=request.headers.get("X-Request-ID", str(uuid.uuid4())),
                    metadata={
                        "path": request.url.path,
                        "method": request.method,
                        "status": response.status_code,
                    },
                )
                await session.commit()

        return response

app.add_middleware(UsageTrackingMiddleware)
```

---

## Quota Enforcement

Enforce usage limits with the quotas module:

```python
from svc_infra.billing.quotas import QuotaService, QuotaExceeded

quota_service = QuotaService(redis_client)

async def check_and_record(tenant_id: str, metric: str, amount: int):
    # Check quota before allowing operation
    try:
        await quota_service.check_and_increment(
            tenant_id=tenant_id,
            metric=metric,
            amount=amount,
            limit=10000,  # Monthly limit
            period="month",
        )
    except QuotaExceeded as e:
        raise HTTPException(
            status_code=429,
            detail=f"Quota exceeded: {e.current}/{e.limit} {metric}",
            headers={"Retry-After": str(e.reset_in_seconds)},
        )

    # Proceed with operation
    await do_billable_operation()
```

### Plan-Based Quotas

```python
async def get_quota_limit(session: AsyncSession, tenant_id: str, metric: str) -> int:
    """Get quota limit from tenant's subscription plan."""

    # Get active subscription
    subscription = await session.execute(
        select(Subscription)
        .where(
            Subscription.tenant_id == tenant_id,
            Subscription.status == "active",
        )
    )
    sub = subscription.scalar_one_or_none()

    if not sub:
        return 0  # No active subscription

    # Get plan entitlement
    entitlement = await session.execute(
        select(PlanEntitlement)
        .where(
            PlanEntitlement.plan_id == sub.plan_id,
            PlanEntitlement.metric == metric,
        )
    )
    ent = entitlement.scalar_one_or_none()

    return ent.included_amount if ent else 0
```

### Soft vs Hard Limits

```python
class QuotaPolicy:
    """Define quota enforcement behavior."""

    HARD = "hard"  # Block when exceeded
    SOFT = "soft"  # Warn but allow (overage charged)

@router.post("/compute")
async def start_compute(
    request: ComputeRequest,
    user = Depends(require_auth),
):
    quota_policy = await get_quota_policy(user.tenant_id, "compute_minutes")
    current_usage = await get_current_usage(user.tenant_id, "compute_minutes")
    limit = await get_quota_limit(session, user.tenant_id, "compute_minutes")

    if current_usage >= limit:
        if quota_policy == QuotaPolicy.HARD:
            raise HTTPException(429, "Compute quota exceeded")
        else:
            # Soft limit: allow but flag for overage billing
            await flag_overage(user.tenant_id, "compute_minutes", current_usage - limit)

    return await start_compute_job(request)
```

---

## Background Jobs

### Daily Aggregation Job

```python
from svc_infra.billing.jobs import register_billing_jobs

# Register with job system
register_billing_jobs(job_system, async_session_maker)

# Or define custom job
@job_system.task(cron="0 1 * * *")  # 1 AM daily
async def aggregate_all_tenants():
    async with async_session_maker() as session:
        tenants = await session.execute(select(Tenant.id))

        for (tenant_id,) in tenants:
            billing = AsyncBillingService(session, tenant_id)
            yesterday = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=1)

            for metric in BILLABLE_METRICS:
                await billing.aggregate_daily(
                    metric=metric,
                    day_start=yesterday,
                )

        await session.commit()
```

### Monthly Invoice Job

```python
@job_system.task(cron="0 2 1 * *")  # 2 AM on 1st of month
async def generate_monthly_invoices():
    async with async_session_maker() as session:
        # Get all active subscriptions
        subscriptions = await session.execute(
            select(Subscription).where(Subscription.status == "active")
        )

        for sub in subscriptions.scalars():
            billing = AsyncBillingService(session, sub.tenant_id)

            # Previous month period
            now = datetime.now(timezone.utc)
            period_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_start = (period_end - timedelta(days=1)).replace(day=1)

            invoice_id = await billing.generate_monthly_invoice(
                period_start=period_start,
                period_end=period_end,
                currency="usd",
            )

            # Sync to payment provider
            await sync_invoice_to_stripe(invoice_id)

        await session.commit()
```

---

## Payment Provider Integration

### Stripe Sync Pattern

svc-infra generates invoices; fin-infra handles Stripe:

```python
from fin_infra.payments import StripeClient

async def sync_invoice_to_stripe(session: AsyncSession, invoice_id: str):
    """Sync svc-infra invoice to Stripe for payment."""

    # Load invoice with lines
    invoice = await session.get(Invoice, invoice_id)
    lines = await session.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
    )

    # Get tenant's Stripe customer ID
    tenant = await session.get(Tenant, invoice.tenant_id)

    stripe = StripeClient()

    # Create Stripe invoice
    stripe_invoice = await stripe.invoices.create(
        customer=tenant.stripe_customer_id,
        auto_advance=True,  # Auto-finalize
        collection_method="charge_automatically",
        metadata={
            "svc_infra_invoice_id": invoice.id,
            "tenant_id": invoice.tenant_id,
        },
    )

    # Add line items
    for line in lines.scalars():
        await stripe.invoice_items.create(
            customer=tenant.stripe_customer_id,
            invoice=stripe_invoice.id,
            quantity=line.quantity,
            unit_amount=line.amount,
            currency=invoice.currency,
            description=f"Usage: {line.metric}" if line.metric else "Subscription",
        )

    # Update invoice with provider reference
    invoice.provider_id = stripe_invoice.id
    invoice.status = "pending"
    await session.commit()

    return stripe_invoice.id
```

### Webhook Handler

```python
from fastapi import Request, HTTPException

@router.post("/webhooks/stripe")
async def handle_stripe_webhook(
    request: Request,
    session = Depends(get_async_session),
):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    if event["type"] == "invoice.paid":
        stripe_invoice_id = event["data"]["object"]["id"]

        # Update our invoice status
        result = await session.execute(
            select(Invoice).where(Invoice.provider_id == stripe_invoice_id)
        )
        invoice = result.scalar_one_or_none()

        if invoice:
            invoice.status = "paid"
            invoice.paid_at = datetime.now(timezone.utc)
            await session.commit()

    elif event["type"] == "invoice.payment_failed":
        stripe_invoice_id = event["data"]["object"]["id"]

        result = await session.execute(
            select(Invoice).where(Invoice.provider_id == stripe_invoice_id)
        )
        invoice = result.scalar_one_or_none()

        if invoice:
            invoice.status = "payment_failed"
            await session.commit()

            # Notify tenant
            await send_payment_failed_notification(invoice.tenant_id)

    return {"status": "ok"}
```

---

## Subscription Management

### Creating Subscriptions

```python
async def create_subscription(
    session: AsyncSession,
    tenant_id: str,
    plan_id: str,
) -> Subscription:
    """Create a new subscription for a tenant."""

    plan = await session.get(Plan, plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")

    # Calculate period based on plan interval
    now = datetime.now(timezone.utc)
    if plan.interval == "month":
        period_end = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    elif plan.interval == "year":
        period_end = now.replace(year=now.year + 1)
    else:
        raise ValueError(f"Unknown interval: {plan.interval}")

    subscription = Subscription(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        plan_id=plan_id,
        status="active",
        current_period_start=now,
        current_period_end=period_end,
        cancel_at_period_end=False,
    )

    session.add(subscription)
    await session.flush()

    return subscription
```

### Plan Changes (Proration)

```python
from decimal import Decimal

async def change_plan(
    session: AsyncSession,
    subscription_id: str,
    new_plan_id: str,
    prorate: bool = True,
) -> Subscription:
    """Change subscription plan with optional proration."""

    subscription = await session.get(Subscription, subscription_id)
    old_plan = await session.get(Plan, subscription.plan_id)
    new_plan = await session.get(Plan, new_plan_id)

    if prorate:
        # Calculate proration
        now = datetime.now(timezone.utc)
        period_days = (subscription.current_period_end - subscription.current_period_start).days
        remaining_days = (subscription.current_period_end - now).days

        # Credit for unused time on old plan
        old_daily_rate = Decimal(old_plan.base_price) / period_days
        credit = old_daily_rate * remaining_days

        # Charge for remaining time on new plan
        new_daily_rate = Decimal(new_plan.base_price) / period_days
        charge = new_daily_rate * remaining_days

        # Net adjustment
        adjustment = charge - credit

        if adjustment != 0:
            await create_proration_invoice_line(
                session,
                subscription.tenant_id,
                amount=int(adjustment * 100),  # Convert to cents
                description=f"Plan change: {old_plan.name} → {new_plan.name}",
            )

    subscription.plan_id = new_plan_id
    await session.commit()

    return subscription
```

### Cancellation

```python
async def cancel_subscription(
    session: AsyncSession,
    subscription_id: str,
    immediate: bool = False,
) -> Subscription:
    """Cancel subscription immediately or at period end."""

    subscription = await session.get(Subscription, subscription_id)

    if immediate:
        subscription.status = "canceled"
        subscription.canceled_at = datetime.now(timezone.utc)

        # Calculate refund if applicable
        if subscription.current_period_end > datetime.now(timezone.utc):
            await process_cancellation_refund(session, subscription)
    else:
        subscription.cancel_at_period_end = True

    await session.commit()
    return subscription
```

---

## Tax Calculation

### Basic Tax Integration

```python
from decimal import Decimal

async def calculate_invoice_with_tax(
    session: AsyncSession,
    invoice_id: str,
    tax_rate: Decimal,
) -> Invoice:
    """Apply tax to invoice total."""

    invoice = await session.get(Invoice, invoice_id)

    subtotal = invoice.total_amount
    tax_amount = int(subtotal * tax_rate)

    invoice.tax_amount = tax_amount
    invoice.total_amount = subtotal + tax_amount

    await session.commit()
    return invoice
```

### Tax Service Integration

```python
# Integration with external tax service (e.g., TaxJar, Avalara)
from fin_infra.tax import TaxCalculator

async def calculate_tax_for_invoice(
    session: AsyncSession,
    invoice_id: str,
    tenant_id: str,
):
    invoice = await session.get(Invoice, invoice_id)
    tenant = await session.get(Tenant, tenant_id)

    tax_calc = TaxCalculator()

    # Get line items
    lines = await session.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
    )

    tax_result = await tax_calc.calculate(
        to_address=tenant.billing_address,
        line_items=[
            {"amount": line.amount, "product_code": line.metric}
            for line in lines.scalars()
        ],
    )

    invoice.tax_amount = tax_result.total_tax
    invoice.tax_breakdown = tax_result.breakdown  # Store for reporting
    invoice.total_amount = invoice.total_amount + tax_result.total_tax

    await session.commit()
```

---

## Testing Billing Flows

### Unit Tests

```python
import pytest
from datetime import datetime, timezone
from svc_infra.billing import AsyncBillingService

@pytest.fixture
async def billing_service(async_session):
    return AsyncBillingService(async_session, tenant_id="test-tenant")

async def test_record_usage(billing_service, async_session):
    event_id = await billing_service.record_usage(
        metric="api_calls",
        amount=5,
        at=datetime.now(timezone.utc),
        idempotency_key="test-key-1",
        metadata={"test": True},
    )

    assert event_id is not None

    # Verify event was created
    event = await async_session.get(UsageEvent, event_id)
    assert event.amount == 5
    assert event.metric == "api_calls"

async def test_idempotent_usage_recording(billing_service, async_session):
    """Same idempotency key should not create duplicate events."""

    await billing_service.record_usage(
        metric="api_calls",
        amount=1,
        at=datetime.now(timezone.utc),
        idempotency_key="same-key",
        metadata={},
    )
    await async_session.commit()

    # Second call with same key should be ignored (depends on DB constraint)
    # Or should return same event_id
```

### Integration Tests

```python
async def test_full_billing_cycle(async_session, stripe_mock):
    """Test complete billing cycle from usage to payment."""

    tenant_id = "test-tenant"
    billing = AsyncBillingService(async_session, tenant_id)

    # 1. Record usage throughout the month
    for i in range(100):
        await billing.record_usage(
            metric="api_calls",
            amount=1,
            at=datetime.now(timezone.utc),
            idempotency_key=f"event-{i}",
            metadata={},
        )

    # 2. Run daily aggregation
    await billing.aggregate_daily(
        metric="api_calls",
        day_start=datetime.now(timezone.utc).replace(hour=0),
    )

    # 3. Generate invoice
    invoice_id = await billing.generate_monthly_invoice(
        period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2024, 2, 1, tzinfo=timezone.utc),
        currency="usd",
    )

    await async_session.commit()

    # 4. Verify invoice
    invoice = await async_session.get(Invoice, invoice_id)
    assert invoice.total_amount == 100
    assert invoice.status == "created"

    # 5. Sync to Stripe (mocked)
    await sync_invoice_to_stripe(async_session, invoice_id)

    await async_session.refresh(invoice)
    assert invoice.provider_id is not None
    assert invoice.status == "pending"
```

---

## Reporting

### Usage Reports

```python
async def generate_usage_report(
    session: AsyncSession,
    tenant_id: str,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Generate comprehensive usage report."""

    billing = AsyncBillingService(session, tenant_id)

    metrics = ["api_calls", "storage_gb", "compute_minutes"]
    report = {
        "tenant_id": tenant_id,
        "period": {"start": start_date, "end": end_date},
        "metrics": {},
    }

    for metric in metrics:
        aggregates = await billing.list_daily_aggregates(
            metric=metric,
            date_from=start_date,
            date_to=end_date,
        )

        total = sum(a.total for a in aggregates)
        daily_avg = total / max(1, len(aggregates))

        report["metrics"][metric] = {
            "total": total,
            "daily_average": round(daily_avg, 2),
            "daily_breakdown": [
                {"date": a.period_start.date().isoformat(), "value": a.total}
                for a in aggregates
            ],
        }

    return report
```

### Financial Reports

```python
async def generate_revenue_report(
    session: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Generate revenue report across all tenants."""

    invoices = await session.execute(
        select(Invoice)
        .where(
            Invoice.status == "paid",
            Invoice.period_start >= start_date,
            Invoice.period_end <= end_date,
        )
    )

    total_revenue = 0
    by_currency = {}

    for invoice in invoices.scalars():
        total_revenue += invoice.total_amount
        by_currency[invoice.currency] = by_currency.get(invoice.currency, 0) + invoice.total_amount

    return {
        "period": {"start": start_date, "end": end_date},
        "total_invoices": len(list(invoices)),
        "total_revenue": total_revenue,
        "by_currency": by_currency,
    }
```

---

## See Also

- [API Integration](api.md) — FastAPI integration patterns
- [Idempotency](idempotency.md) — Preventing duplicate charges
- [Jobs](jobs.md) — Background job scheduling
- [fin-infra Payments](https://fin-infra.nfrax.com/payments) — Payment processing with Stripe
