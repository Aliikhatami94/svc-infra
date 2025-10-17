import pytest

from svc_infra.db.outbox import InMemoryOutboxStore
from svc_infra.jobs.builtins.outbox_processor import make_outbox_tick
from svc_infra.jobs.queue import InMemoryJobQueue

pytestmark = pytest.mark.jobs


@pytest.mark.asyncio
async def test_outbox_tick_enqueues_job():
    outbox = InMemoryOutboxStore()
    queue = InMemoryJobQueue()
    # enqueue two topics
    outbox.enqueue("invoice.created", {"id": "inv_1"})
    outbox.enqueue("customer.created", {"id": "cus_1"})
    tick = make_outbox_tick(outbox, queue)
    # First tick moves first message
    await tick()
    j1 = queue.reserve_next()
    assert j1 is not None
    assert j1.name == "outbox.invoice.created"
    assert j1.payload["outbox_id"] == 1
    # acknowledge the first job before fetching the next
    queue.ack(j1.id)
    # Second tick moves second message
    await tick()
    j2 = queue.reserve_next()
    assert j2 is not None
    assert j2.name == "outbox.customer.created"
    assert j2.payload["outbox_id"] == 2
