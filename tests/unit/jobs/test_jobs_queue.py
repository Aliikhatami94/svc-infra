from __future__ import annotations

import asyncio

import pytest

from svc_infra.jobs.easy import easy_jobs
from svc_infra.jobs.queue import InMemoryJobQueue
from svc_infra.jobs.worker import process_one

pytestmark = pytest.mark.jobs


@pytest.mark.asyncio
async def test_enqueue_and_process_success():
    queue, _sched = easy_jobs()

    # Enqueue a job
    queue.enqueue("say-hello", {"name": "alice"})

    # Process
    processed = await process_one(queue, handler=lambda job: asyncio.sleep(0))
    assert processed is True

    # Queue empty
    processed = await process_one(queue, handler=lambda job: asyncio.sleep(0))
    assert processed is False


@pytest.mark.asyncio
async def test_fail_and_backoff_requeues_job():
    q = InMemoryJobQueue()
    q.enqueue("task", {})

    # First attempt fails: next available should be in the future
    async def boom(job):
        raise RuntimeError("boom")

    await process_one(q, handler=boom)

    # Immediately try to reserve again -> no job available due to backoff
    nxt = q.reserve_next()
    assert nxt is None


@pytest.mark.asyncio
async def test_delayed_enqueue_and_reserve():
    q = InMemoryJobQueue()
    q.enqueue("delayed", {}, delay_seconds=1)

    # Should not be available immediately
    assert q.reserve_next() is None
