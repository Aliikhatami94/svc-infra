import asyncio
import time

import pytest

from svc_infra.jobs.queue import InMemoryJobQueue
from svc_infra.jobs.runner import WorkerRunner


@pytest.mark.asyncio
async def test_worker_runner_graceful_stop_allows_inflight_to_finish():
    q = InMemoryJobQueue()
    q.enqueue("t", {})

    async def handler(job):
        await asyncio.sleep(0.1)

    runner = WorkerRunner(q, handler, poll_interval=0.01)
    runner.start()
    t0 = time.time()
    await runner.stop(grace_seconds=0.5)
    t1 = time.time()
    # Stopped and did not exceed grace
    assert (t1 - t0) < 0.6
    # Queue should be empty (acked)
    assert q.reserve_next() is None


@pytest.mark.asyncio
async def test_worker_runner_stop_timeout_does_not_hang():
    q = InMemoryJobQueue()
    q.enqueue("t", {})

    async def handler(job):
        await asyncio.sleep(0.5)

    runner = WorkerRunner(q, handler, poll_interval=0.01)
    runner.start()
    t0 = time.time()
    await runner.stop(grace_seconds=0.05)
    t1 = time.time()
    # Should return quickly (grace respected)
    assert (t1 - t0) < 0.2
