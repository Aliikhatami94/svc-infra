"""Async Billing Service - Primary billing API.

This is the recommended billing service for all new code. It provides
full async/await support for usage tracking, aggregation, and invoicing.

Usage:
    from svc_infra.billing import AsyncBillingService

    async with async_session_maker() as session:
        service = AsyncBillingService(session, tenant_id="tenant_123")
        await service.record_usage(
            metric="api_calls",
            amount=1,
            at=datetime.now(timezone.utc),
            idempotency_key="unique-key",
            metadata={"endpoint": "/api/v1/users"},
        )

See also:
    - models: Invoice, UsageEvent, UsageAggregate, etc.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Invoice, InvoiceLine, UsageAggregate, UsageEvent


class AsyncBillingService:
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    async def record_usage(
        self,
        *,
        metric: str,
        amount: int,
        at: datetime,
        idempotency_key: str,
        metadata: dict | None,
    ) -> str:
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        evt = UsageEvent(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            metric=metric,
            amount=amount,
            at_ts=at,
            idempotency_key=idempotency_key,
            metadata_json=metadata or {},
        )
        self.session.add(evt)
        await self.session.flush()
        return evt.id

    async def aggregate_daily(self, *, metric: str, day_start: datetime) -> int:
        day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC)
        next_day = day_start + timedelta(days=1)
        total = 0
        rows: Sequence[UsageEvent] = (
            (
                await self.session.execute(
                    select(UsageEvent).where(
                        UsageEvent.tenant_id == self.tenant_id,
                        UsageEvent.metric == metric,
                        UsageEvent.at_ts >= day_start,
                        UsageEvent.at_ts < next_day,
                    )
                )
            )
            .scalars()
            .all()
        )
        for r in rows:
            total += int(r.amount)

        agg = (
            await self.session.execute(
                select(UsageAggregate).where(
                    UsageAggregate.tenant_id == self.tenant_id,
                    UsageAggregate.metric == metric,
                    UsageAggregate.period_start == day_start,
                    UsageAggregate.granularity == "day",
                )
            )
        ).scalar_one_or_none()
        if agg:
            agg.total = total
        else:
            self.session.add(
                UsageAggregate(
                    id=str(uuid.uuid4()),
                    tenant_id=self.tenant_id,
                    metric=metric,
                    period_start=day_start,
                    granularity="day",
                    total=total,
                )
            )
        return total

    async def list_daily_aggregates(
        self, *, metric: str, date_from: datetime | None, date_to: datetime | None
    ) -> list[UsageAggregate]:
        q = select(UsageAggregate).where(
            UsageAggregate.tenant_id == self.tenant_id,
            UsageAggregate.metric == metric,
            UsageAggregate.granularity == "day",
        )
        if date_from is not None:
            q = q.where(UsageAggregate.period_start >= date_from)
        if date_to is not None:
            q = q.where(UsageAggregate.period_start < date_to)
        rows = list((await self.session.execute(q)).scalars().all())
        return rows

    async def generate_monthly_invoice(
        self, *, period_start: datetime, period_end: datetime, currency: str
    ) -> str:
        total = 0
        aggs: Sequence[UsageAggregate] = (
            (
                await self.session.execute(
                    select(UsageAggregate).where(
                        UsageAggregate.tenant_id == self.tenant_id,
                        UsageAggregate.period_start >= period_start,
                        UsageAggregate.period_start < period_end,
                        UsageAggregate.granularity == "day",
                    )
                )
            )
            .scalars()
            .all()
        )
        for r in aggs:
            total += int(r.total)

        inv = Invoice(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            period_start=period_start,
            period_end=period_end,
            status="created",
            total_amount=total,
            currency=currency,
        )
        self.session.add(inv)
        await self.session.flush()

        line = InvoiceLine(
            id=str(uuid.uuid4()),
            invoice_id=inv.id,
            price_id=None,
            metric=None,
            quantity=1,
            amount=total,
        )
        self.session.add(line)
        return inv.id
