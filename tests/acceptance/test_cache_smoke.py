from __future__ import annotations

import asyncio

import pytest

from svc_infra.cache.decorators import cache_read, cache_write, init_cache


@pytest.mark.acceptance
def test_cache_read_write_smoke_in_memory_backend():
    # Initialize default (in-memory) backend
    init_cache()

    calls = {"get": 0}

    @cache_read(key="thing:{id}", ttl=1)
    async def get_thing(*, id: int):
        calls["get"] += 1
        return {"id": id, "v": calls["get"]}

    @cache_write(tags=["thing:{id}"])
    async def set_thing(*, id: int, v: int):
        return {"id": id, "v": v}

    # First call → miss, compute
    v1 = asyncio.get_event_loop().run_until_complete(get_thing(id=1))
    assert v1 == {"id": 1, "v": 1}

    # Second call → hit (no new compute)
    v2 = asyncio.get_event_loop().run_until_complete(get_thing(id=1))
    assert v2 == {"id": 1, "v": 1}

    # Mutate → invalidates tag, next read recomputes
    asyncio.get_event_loop().run_until_complete(set_thing(id=1, v=99))
    v3 = asyncio.get_event_loop().run_until_complete(get_thing(id=1))
    assert v3 == {"id": 1, "v": 2}
