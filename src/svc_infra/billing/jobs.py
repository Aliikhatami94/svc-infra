from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from svc_infra.jobs.queue import Job, JobQueue
from svc_infra.jobs.scheduler import InMemoryScheduler
from svc_infra.webhooks.service import WebhookService

from .async_service import AsyncBillingService


async def job_aggregate_daily(
    session: AsyncSession, *, tenant_id: str, metric: str, day_start: datetime
) -> None:
    """
    Aggregate usage for a tenant/metric for the given day_start (UTC).

    Intended to be called from a scheduler/worker with an AsyncSession created by the host app.
    """
    svc = AsyncBillingService(session=session, tenant_id=tenant_id)
    if day_start.tzinfo is None:
        day_start = day_start.replace(tzinfo=timezone.utc)
    await svc.aggregate_daily(metric=metric, day_start=day_start)


async def job_generate_monthly_invoice(
    session: AsyncSession,
    *,
    tenant_id: str,
    period_start: datetime,
    period_end: datetime,
    currency: str,
) -> str:
    """
    Generate a monthly invoice for a tenant between [period_start, period_end).
    Returns the internal invoice id.
    """
    svc = AsyncBillingService(session=session, tenant_id=tenant_id)
    if period_start.tzinfo is None:
        period_start = period_start.replace(tzinfo=timezone.utc)
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)
    return await svc.generate_monthly_invoice(
        period_start=period_start, period_end=period_end, currency=currency
    )


# -------- Job helpers and handlers (scheduler/worker wiring) ---------

BILLING_AGGREGATE_JOB = "billing.aggregate_daily"
BILLING_INVOICE_JOB = "billing.generate_monthly_invoice"


def enqueue_aggregate_daily(
    queue: JobQueue,
    *,
    tenant_id: str,
    metric: str,
    day_start: datetime,
    delay_seconds: int = 0,
) -> None:
    payload = {
        "tenant_id": tenant_id,
        "metric": metric,
        "day_start": day_start.astimezone(timezone.utc).isoformat(),
    }
    queue.enqueue(BILLING_AGGREGATE_JOB, payload, delay_seconds=delay_seconds)


def enqueue_generate_monthly_invoice(
    queue: JobQueue,
    *,
    tenant_id: str,
    period_start: datetime,
    period_end: datetime,
    currency: str,
    delay_seconds: int = 0,
) -> None:
    payload = {
        "tenant_id": tenant_id,
        "period_start": period_start.astimezone(timezone.utc).isoformat(),
        "period_end": period_end.astimezone(timezone.utc).isoformat(),
        "currency": currency,
    }
    queue.enqueue(BILLING_INVOICE_JOB, payload, delay_seconds=delay_seconds)


def make_daily_aggregate_tick(
    queue: JobQueue,
    *,
    tenant_id: str,
    metric: str,
    when: Optional[datetime] = None,
):
    """Return an async function that enqueues a daily aggregate job.

    This is a simple helper for local/dev schedulers; it schedules an aggregate
    for the UTC day of ``when`` (or now). Call repeatedly via a scheduler.
    """

    async def _tick():
        ts = (when or datetime.now(timezone.utc)).astimezone(timezone.utc)
        day_start = ts.replace(hour=0, minute=0, second=0, microsecond=0)
        enqueue_aggregate_daily(queue, tenant_id=tenant_id, metric=metric, day_start=day_start)

    return _tick


def make_billing_job_handler(
    *,
    session_factory: "async_sessionmaker[AsyncSession]",
    webhooks: WebhookService,
) -> Callable[[Job], Awaitable[None]]:
    """Create a worker handler that processes billing jobs and emits webhooks.

    Supported jobs and their expected payloads:
    - billing.aggregate_daily {tenant_id, metric, day_start: ISO8601}
      → emits topic 'billing.usage_aggregated'
    - billing.generate_monthly_invoice {tenant_id, period_start: ISO8601, period_end: ISO8601, currency}
      → emits topic 'billing.invoice.created'
    """

    async def _maybe_commit(session: Any) -> None:
        """Commit if the session exposes a commit method (await if coroutine).

        This makes the handler resilient in tests/dev where a dummy session is used.
        """
        commit = getattr(session, "commit", None)
        if callable(commit):
            result = commit()
            if inspect.isawaitable(result):
                await result

    async def _handler(job: Job) -> None:
        name = job.name
        data: Dict[str, Any] = job.payload or {}
        if name == BILLING_AGGREGATE_JOB:
            tenant_id = str(data.get("tenant_id"))
            metric = str(data.get("metric"))
            day_raw = data.get("day_start")
            if not tenant_id or not metric or not day_raw:
                return
            day_start = datetime.fromisoformat(str(day_raw))
            async with session_factory() as session:
                svc = AsyncBillingService(session=session, tenant_id=tenant_id)
                total = await svc.aggregate_daily(metric=metric, day_start=day_start)
                await _maybe_commit(session)
            webhooks.publish(
                "billing.usage_aggregated",
                {
                    "tenant_id": tenant_id,
                    "metric": metric,
                    "day_start": day_start.astimezone(timezone.utc).isoformat(),
                    "total": int(total),
                },
            )
            return
        if name == BILLING_INVOICE_JOB:
            tenant_id = str(data.get("tenant_id"))
            period_start_raw = data.get("period_start")
            period_end_raw = data.get("period_end")
            currency = str(data.get("currency"))
            if not tenant_id or not period_start_raw or not period_end_raw or not currency:
                return
            period_start = datetime.fromisoformat(str(period_start_raw))
            period_end = datetime.fromisoformat(str(period_end_raw))
            async with session_factory() as session:
                svc = AsyncBillingService(session=session, tenant_id=tenant_id)
                invoice_id = await svc.generate_monthly_invoice(
                    period_start=period_start, period_end=period_end, currency=currency
                )
                await _maybe_commit(session)
            webhooks.publish(
                "billing.invoice.created",
                {
                    "tenant_id": tenant_id,
                    "invoice_id": invoice_id,
                    "period_start": period_start.astimezone(timezone.utc).isoformat(),
                    "period_end": period_end.astimezone(timezone.utc).isoformat(),
                    "currency": currency,
                },
            )
            return
        # Ignore unrelated jobs

    return _handler


def add_billing_jobs(
    *,
    scheduler: InMemoryScheduler,
    queue: JobQueue,
    jobs: list[dict],
) -> None:
    """Register simple interval-based billing job enqueuers.

    jobs: list of dicts with shape {"name": "aggregate", "tenant_id": ..., "metric": ..., "interval_seconds": 86400}
          or {"name": "invoice", "tenant_id": ..., "period_start": ISO, "period_end": ISO, "currency": ..., "interval_seconds": 2592000}
    """

    for j in jobs:
        name = j.get("name")
        interval = int(j.get("interval_seconds", 86400))
        if name == "aggregate":
            tenant_id = j["tenant_id"]
            metric = j["metric"]

            async def _tick_fn(tid=tenant_id, m=metric):
                # Enqueue for the current UTC day
                now = datetime.now(timezone.utc)
                day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                enqueue_aggregate_daily(queue, tenant_id=tid, metric=m, day_start=day_start)

            scheduler.add_task(f"billing.aggregate.{tenant_id}.{metric}", interval, _tick_fn)
        elif name == "invoice":
            tenant_id = j["tenant_id"]
            currency = j["currency"]
            pstart = datetime.fromisoformat(j["period_start"]).astimezone(timezone.utc)
            pend = datetime.fromisoformat(j["period_end"]).astimezone(timezone.utc)

            async def _tick_inv(tid=tenant_id, cs=currency, ps=pstart, pe=pend):
                enqueue_generate_monthly_invoice(
                    queue, tenant_id=tid, period_start=ps, period_end=pe, currency=cs
                )

            scheduler.add_task(f"billing.invoice.{tenant_id}", interval, _tick_inv)
