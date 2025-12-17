from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.jobs.queue import InMemoryJobQueue
from svc_infra.jobs.scheduler import InMemoryScheduler
from svc_infra.webhooks import add_webhooks
from svc_infra.webhooks import router as router_module


def test_add_webhooks_mounts_router_and_reuses_dependencies():
    app = FastAPI()
    add_webhooks(app)

    client = TestClient(app)
    resp = client.post(
        "/_webhooks/subscriptions",
        json={
            "topic": "invoice.created",
            "url": "https://example.test",
            "secret": "sekrit",
        },
    )
    assert resp.status_code == 200

    outbox_override = app.dependency_overrides[router_module.get_outbox]
    subs_override = app.dependency_overrides[router_module.get_subs]

    outbox_one = outbox_override()
    outbox_two = outbox_override()
    assert outbox_one is outbox_two
    assert app.state.webhooks_outbox is outbox_one

    subs_one = subs_override()
    subs_two = subs_override()
    assert subs_one is subs_two
    assert app.state.webhooks_subscriptions is subs_one


@pytest.mark.asyncio
async def test_add_webhooks_registers_tick_and_handler():
    app = FastAPI()
    queue = InMemoryJobQueue()
    scheduler = InMemoryScheduler()

    add_webhooks(app, queue=queue, scheduler=scheduler)

    # Tick task should be registered and callable
    task = scheduler._tasks.get("webhooks.outbox")
    assert task is not None
    await task.func()  # no messages enqueued yet – should be a no-op

    assert hasattr(app.state, "webhooks_outbox_tick")
    assert callable(app.state.webhooks_outbox_tick)

    handler = getattr(app.state, "webhooks_delivery_handler", None)
    assert handler is not None

    # Dependency override still returns the same outbox instance the handler will use
    outbox_override = app.dependency_overrides[router_module.get_outbox]
    assert outbox_override() is app.state.webhooks_outbox
