from __future__ import annotations

import asyncio

import pytest

from svc_infra.data.erasure import ErasurePlan, ErasureStep, run_erasure

pytestmark = pytest.mark.data_lifecycle


class FakeSession:
    async def execute(self, stmt):
        return None


@pytest.mark.asyncio
async def test_run_erasure_with_sync_and_async_steps():
    sess = FakeSession()
    calls: list[str] = []

    def s1(session, pid):
        assert pid == "user_1"
        calls.append("s1")
        return 1

    async def s2(session, pid):
        await asyncio.sleep(0)
        calls.append("s2")
        return 2

    events: list[tuple[str, dict]] = []

    def audit(evt: str, ctx: dict):
        events.append((evt, ctx))

    plan = ErasurePlan(steps=[ErasureStep("s1", s1), ErasureStep("s2", s2)])
    total = await run_erasure(sess, "user_1", plan, on_audit=audit)

    assert total == 3
    assert calls == ["s1", "s2"]
    assert events and events[0][0] == "erasure.completed" and events[0][1]["affected"] == 3
