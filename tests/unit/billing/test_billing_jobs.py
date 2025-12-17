from datetime import datetime, timezone

import pytest

from svc_infra.billing import jobs as jobs_module
from svc_infra.billing.jobs import (
    BILLING_AGGREGATE_JOB,
    BILLING_INVOICE_JOB,
    make_billing_job_handler,
)
from svc_infra.db.outbox import InMemoryOutboxStore
from svc_infra.jobs.queue import InMemoryJobQueue
from svc_infra.webhooks.service import InMemoryWebhookSubscriptions, WebhookService

pytestmark = pytest.mark.billing


class _FakeAsyncBillingService:
    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    async def aggregate_daily(self, *, metric: str, day_start: datetime) -> int:
        # Return a fixed total to assert webhook payload
        return 5

    async def generate_monthly_invoice(
        self, *, period_start: datetime, period_end: datetime, currency: str
    ) -> str:
        # Return a deterministic invoice id
        return "inv_test_1"


class _DummySessionCtx:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *a):
        return False


def _dummy_session_factory():
    return _DummySessionCtx()


@pytest.mark.asyncio
async def test_billing_aggregate_job_emits_webhook(monkeypatch):
    # Monkeypatch the service used by the handler
    monkeypatch.setattr(jobs_module, "AsyncBillingService", _FakeAsyncBillingService)

    outbox = InMemoryOutboxStore()
    subs = InMemoryWebhookSubscriptions()
    subs.add(
        "billing.usage_aggregated", url="https://example.test/hook", secret="sekrit"
    )
    webhooks = WebhookService(outbox=outbox, subs=subs)

    # Spy on publish
    calls = []
    orig_publish = webhooks.publish

    def _spy_publish(topic, payload, *, version=1):
        calls.append((topic, payload))
        return orig_publish(topic, payload, version=version)

    webhooks.publish = _spy_publish  # type: ignore[method-assign]

    handler = make_billing_job_handler(
        session_factory=_dummy_session_factory, webhooks=webhooks
    )

    queue = InMemoryJobQueue()
    payload = {
        "tenant_id": "t1",
        "metric": "tokens",
        "day_start": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
    }
    queue.enqueue(BILLING_AGGREGATE_JOB, payload)

    # Call handler directly to surface exceptions if any
    job = queue.reserve_next()
    assert job is not None
    await handler(job)
    # Ack like the worker would
    queue.ack(job.id)

    # Assert publish was called and message was enqueued
    assert any(t == "billing.usage_aggregated" for (t, _) in calls)
    msgs = getattr(outbox, "_messages", [])
    assert len(msgs) >= 1
    msg = msgs[0]
    event = (
        msg.payload["event"]
        if isinstance(msg.payload, dict) and "event" in msg.payload
        else msg.payload
    )
    assert event["topic"] == "billing.usage_aggregated"
    assert event["payload"]["tenant_id"] == "t1"
    assert event["payload"]["metric"] == "tokens"
    assert int(event["payload"]["total"]) == 5


@pytest.mark.asyncio
async def test_billing_invoice_job_emits_webhook(monkeypatch):
    # Monkeypatch the service used by the handler
    monkeypatch.setattr(jobs_module, "AsyncBillingService", _FakeAsyncBillingService)

    outbox = InMemoryOutboxStore()
    subs = InMemoryWebhookSubscriptions()
    subs.add("billing.invoice.created", url="https://example.test/inv", secret="sekrit")
    webhooks = WebhookService(outbox=outbox, subs=subs)

    # Spy on publish
    calls = []
    orig_publish = webhooks.publish

    def _spy_publish(topic, payload, *, version=1):
        calls.append((topic, payload))
        return orig_publish(topic, payload, version=version)

    webhooks.publish = _spy_publish  # type: ignore[method-assign]

    handler = make_billing_job_handler(
        session_factory=_dummy_session_factory, webhooks=webhooks
    )

    queue = InMemoryJobQueue()
    payload = {
        "tenant_id": "t1",
        "period_start": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "period_end": datetime(2025, 2, 1, tzinfo=timezone.utc).isoformat(),
        "currency": "usd",
    }
    queue.enqueue(BILLING_INVOICE_JOB, payload)

    job = queue.reserve_next()
    assert job is not None
    await handler(job)
    queue.ack(job.id)

    assert any(t == "billing.invoice.created" for (t, _) in calls)
    msgs = getattr(outbox, "_messages", [])
    assert len(msgs) >= 1
    msg = msgs[0]
    event = (
        msg.payload["event"]
        if isinstance(msg.payload, dict) and "event" in msg.payload
        else msg.payload
    )
    assert event["topic"] == "billing.invoice.created"
    pl = event["payload"]
    assert pl["tenant_id"] == "t1"
    assert pl["currency"] == "usd"
    assert pl["invoice_id"] == "inv_test_1"
