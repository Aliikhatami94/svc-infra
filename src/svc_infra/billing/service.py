from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Invoice, InvoiceLine, UsageAggregate, UsageEvent

ProviderSyncHook = Callable[[Invoice, list[InvoiceLine]], None]


@dataclass
class BillingService:
    session: Session
    tenant_id: str
    provider_sync: Optional[ProviderSyncHook] = None

    def record_usage(
        self, *, metric: str, amount: int, at: datetime, idempotency_key: str, metadata: dict | None
    ) -> str:
        # Ensure UTC
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
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
        self.session.flush()
        return evt.id

    def aggregate_daily(self, *, metric: str, day_start: datetime) -> None:
        # Compute [day_start, day_start+1d)
        next_day = day_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        total = 0
        rows = self.session.execute(
            select(UsageEvent).where(
                UsageEvent.tenant_id == self.tenant_id,
                UsageEvent.metric == metric,
                UsageEvent.at_ts >= day_start,
                UsageEvent.at_ts < next_day,
            )
        ).scalars()
        for r in rows:
            total += int(r.amount)
        # upsert aggregate
        agg = self.session.execute(
            select(UsageAggregate).where(
                UsageAggregate.tenant_id == self.tenant_id,
                UsageAggregate.metric == metric,
                UsageAggregate.period_start == day_start,
                UsageAggregate.granularity == "day",
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

    def generate_monthly_invoice(
        self, *, period_start: datetime, period_end: datetime, currency: str
    ) -> str:
        # Minimal: sum all daily aggregates and produce one line
        total = 0
        rows = self.session.execute(
            select(UsageAggregate).where(
                UsageAggregate.tenant_id == self.tenant_id,
                UsageAggregate.period_start >= period_start,
                UsageAggregate.period_start < period_end,
                UsageAggregate.granularity == "day",
            )
        ).scalars()
        for r in rows:
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
        self.session.flush()
        line = InvoiceLine(
            id=str(uuid.uuid4()),
            invoice_id=inv.id,
            price_id=None,
            metric=None,
            quantity=1,
            amount=total,
        )
        self.session.add(line)
        if self.provider_sync:
            self.provider_sync(inv, [line])
        return inv.id
