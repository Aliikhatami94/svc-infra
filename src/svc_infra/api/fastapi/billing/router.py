from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Response, status

from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.middleware.idempotency import require_idempotency_key
from svc_infra.api.fastapi.tenancy.context import TenantId
from svc_infra.billing.async_service import AsyncBillingService
from svc_infra.billing.schemas import UsageAckOut, UsageAggregateRow, UsageAggregatesOut, UsageIn

router = APIRouter(prefix="/_billing", tags=["Billing"])


def get_service(tenant_id: TenantId, session: SqlSessionDep) -> AsyncBillingService:
    return AsyncBillingService(session=session, tenant_id=tenant_id)


@router.post(
    "/usage",
    name="billing_record_usage",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UsageAckOut,
    dependencies=[Depends(require_idempotency_key)],
)
async def record_usage(
    data: UsageIn, svc: Annotated[AsyncBillingService, Depends(get_service)], response: Response
):
    at = data.at or datetime.now(tz=timezone.utc)
    evt_id = await svc.record_usage(
        metric=data.metric,
        amount=int(data.amount),
        at=at,
        idempotency_key=data.idempotency_key,
        metadata=data.metadata,
    )
    # For 202, no Location header is required, but we can surface the id in the body
    return UsageAckOut(id=evt_id, accepted=True)


@router.get(
    "/usage",
    name="billing_list_aggregates",
    response_model=UsageAggregatesOut,
)
async def list_aggregates(
    metric: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    svc: Annotated[AsyncBillingService, Depends(get_service)] = None,
):
    rows = await svc.list_daily_aggregates(metric=metric, date_from=date_from, date_to=date_to)
    items = [
        UsageAggregateRow(
            period_start=r.period_start,
            granularity=r.granularity,
            metric=r.metric,
            total=int(r.total),
        )
        for r in rows
    ]
    return UsageAggregatesOut(items=items, next_cursor=None)
