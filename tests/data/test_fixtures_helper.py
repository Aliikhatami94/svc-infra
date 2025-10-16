from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from svc_infra.data.fixtures import make_on_load_fixtures, run_fixtures

pytestmark = pytest.mark.data_lifecycle


@pytest.mark.asyncio
async def test_run_fixtures_sync_and_async(tmp_path: Path):
    calls: list[str] = []

    def f1():
        calls.append("f1")

    async def f2():
        await asyncio.sleep(0)
        calls.append("f2")

    await run_fixtures([f1, f2])
    assert calls == ["f1", "f2"]


@pytest.mark.asyncio
async def test_make_on_load_fixtures_run_once(tmp_path: Path):
    calls: list[str] = []
    sentinel = tmp_path / "fixtures" / ".done"

    def f():
        calls.append("f")

    on_load = make_on_load_fixtures(f, run_once_file=str(sentinel))

    # first run executes and creates sentinel
    await on_load()
    assert calls == ["f"]
    assert sentinel.exists()

    # second run should be a no-op
    await on_load()
    assert calls == ["f"]
