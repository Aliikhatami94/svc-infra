from __future__ import annotations

import pytest

from svc_infra.db.inbox import InMemoryInboxStore
from svc_infra.db.outbox import InMemoryOutboxStore


@pytest.mark.concurrency
class TestOutboxInbox:
    def test_outbox_enqueue_fetch_mark(self):
        ob = InMemoryOutboxStore()
        m1 = ob.enqueue("orders", {"id": 1})
        m2 = ob.enqueue("orders", {"id": 2})

        nxt = ob.fetch_next()
        assert nxt and nxt.id == m1.id
        ob.mark_processed(nxt.id)

        nxt2 = ob.fetch_next()
        assert nxt2 and nxt2.id == m2.id
        ob.mark_failed(nxt2.id)
        assert nxt2.attempts == 1

        # After processed both, no more
        ob.mark_processed(nxt2.id)
        assert ob.fetch_next() is None

    def test_outbox_topic_filter(self):
        ob = InMemoryOutboxStore()
        m1 = ob.enqueue("orders", {"id": 1})
        ob.enqueue("billing", {"id": 99})

        nxt = ob.fetch_next(topics=["billing"])
        assert nxt and nxt.topic == "billing"

    def test_inbox_mark_if_new(self):
        ib = InMemoryInboxStore()
        assert ib.mark_if_new("foo") is True
        assert ib.mark_if_new("foo") is False
        # Purge shouldn’t remove non-expired yet
        assert ib.purge_expired() in (0,)
