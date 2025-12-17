from __future__ import annotations

import pytest

from svc_infra.jobs.scheduler import InMemoryScheduler

pytestmark = pytest.mark.jobs


@pytest.mark.asyncio
async def test_scheduler_runs_task_on_tick():
    ran = False

    async def task():
        nonlocal ran
        ran = True

    s = InMemoryScheduler()
    s.add_task("t1", interval_seconds=0, func=task)

    await s.tick()
    assert ran is True
