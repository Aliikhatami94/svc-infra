import asyncio
import time

import pytest

from svc_infra.jobs.queue import InMemoryJobQueue
from svc_infra.jobs.worker import process_one


@pytest.mark.asyncio
async def test_worker_times_out_and_fails_job(monkeypatch):
    # Set a very small timeout
    monkeypatch.setenv("JOB_DEFAULT_TIMEOUT_SECONDS", "0.05")

    q = InMemoryJobQueue()
    job = q.enqueue("sleepy", {"n": 1})

    async def sleepy_handler(_job):
        await asyncio.sleep(0.2)

    t0 = time.time()
    processed = await process_one(q, sleepy_handler)
    t1 = time.time()

    assert processed is True
    # Job should not be acked; still in queue with attempts == 1 and last_error set
    # but its availability pushed into the future due to backoff.
    # Access internal list for simplicity in this unit test.
    remaining = [j for j in q._jobs if j.id == job.id]
    assert len(remaining) == 1
    j = remaining[0]
    assert j.attempts == 1
    assert j.last_error is not None
    # Ensure we didn't wait the full sleep; timeout triggered earlier (~0.05s)
    assert (t1 - t0) < 0.2
