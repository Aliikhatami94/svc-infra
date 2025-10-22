from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.tenancy.context import TenantId

from .models import PlanEntitlement, Subscription, UsageAggregate


async def _current_subscription(session: AsyncSession, tenant_id: str) -> Optional[Subscription]:
    now = datetime.now(tz=timezone.utc)
    row = (
        (
            await session.execute(
                select(Subscription)
                .where(Subscription.tenant_id == tenant_id)
                .order_by(Subscription.effective_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        return None
    # basic check: if ended_at is set and in the past, treat as inactive
    if row.ended_at is not None and row.ended_at <= now:
        return None
    return row


def require_quota(metric: str, *, window: str = "day", soft: bool = True):
    async def _dep(tenant_id: TenantId, session: SqlSessionDep) -> None:
        sub = await _current_subscription(session, tenant_id)
        if sub is None:
            # no subscription → allow (unlimited) by default
            return
        ent = (
            (
                await session.execute(
                    select(PlanEntitlement).where(
                        PlanEntitlement.plan_id == sub.plan_id,
                        PlanEntitlement.key == metric,
                        PlanEntitlement.window == window,
                    )
                )
            )
            .scalars()
            .first()
        )
        if ent is None:
            # no entitlement → unlimited
            return
        # compute current window start
        now = datetime.now(tz=timezone.utc)
        if window == "day":
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            granularity = "day"
        elif window == "month":
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            granularity = "month"  # we only aggregate per day, but future-proof
        else:
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            granularity = "day"

        used_row = (
            (
                await session.execute(
                    select(UsageAggregate).where(
                        UsageAggregate.tenant_id == tenant_id,
                        UsageAggregate.metric == metric,
                        UsageAggregate.granularity == granularity,  # v1 daily baseline
                        UsageAggregate.period_start == period_start,
                    )
                )
            )
            .scalars()
            .first()
        )
        used = int(used_row.total) if used_row else 0
        limit_ = int(ent.limit_per_window)
        if used >= limit_:
            if soft:
                # allow but signal overage via header later (TODO: add header hook)
                return
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Quota exceeded for {metric} in {window} window",
            )

    return _dep


QuotaDep = Annotated[None, Depends(require_quota)]

__all__ = ["require_quota"]
