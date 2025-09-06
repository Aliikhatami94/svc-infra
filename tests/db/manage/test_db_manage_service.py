from __future__ import annotations

import pytest
from typing import Any, Sequence

from svc_infra.db.manage.service import Service


class DummyRepo:
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    async def list(self, session, *, limit: int, offset: int, order_by: Sequence[Any] | None = None):
        self.calls.append(("list", (session,), {"limit": limit, "offset": offset, "order_by": order_by}))
        return [
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
        ]

    async def count(self, session):
        self.calls.append(("count", (session,), {}))
        return 2

    async def get(self, session, id_value):
        self.calls.append(("get", (session, id_value), {}))
        return {"id": id_value, "name": "x"}

    async def create(self, session, data: dict[str, Any]):
        self.calls.append(("create", (session,), {"data": data}))
        return {"id": 10, **data}

    async def update(self, session, id_value, data: dict[str, Any]):
        self.calls.append(("update", (session, id_value), {"data": data}))
        return {"id": id_value, **data}

    async def delete(self, session, id_value):
        self.calls.append(("delete", (session, id_value), {}))
        return True

    async def search(self, session, *, q: str, fields: Sequence[str], limit: int, offset: int, order_by: Sequence[Any] | None = None):
        self.calls.append(("search", (session,), {"q": q, "fields": fields, "limit": limit, "offset": offset, "order_by": order_by}))
        return []

    async def count_filtered(self, session, *, q: str, fields: Sequence[str]):
        self.calls.append(("count_filtered", (session,), {"q": q, "fields": fields}))
        return 0

    async def exists(self, session, *, where):
        self.calls.append(("exists", (session,), {"where": where}))
        return True


@pytest.mark.asyncio
async def test_service_pass_through_and_hooks():
    class MyService(Service):
        async def pre_create(self, data: dict[str, Any]) -> dict[str, Any]:
            data = dict(data)
            data["touched"] = True
            return data

        async def pre_update(self, data: dict[str, Any]) -> dict[str, Any]:
            data = dict(data)
            data["updated"] = True
            return data

    repo = DummyRepo()
    svc = MyService(repo)
    session = object()

    # list/count
    items = await svc.list(session, limit=5, offset=0, order_by=[("name", "asc")])
    total = await svc.count(session)
    assert len(items) == 2 and total == 2

    # get
    row = await svc.get(session, 123)
    assert row["id"] == 123

    # create applies pre_create
    created = await svc.create(session, {"name": "z"})
    assert created["touched"] is True

    # update applies pre_update
    updated = await svc.update(session, 10, {"name": "n"})
    assert updated["updated"] is True and updated["id"] == 10

    # delete
    assert await svc.delete(session, 10) is True

    # search & count_filtered
    _ = await svc.search(session, q="foo", fields=["name"], limit=10, offset=0, order_by=None)
    _ = await svc.count_filtered(session, q="foo", fields=["name"])

    # exists
    assert await svc.exists(session, where=[("x", "=", 1)]) is True

    # sanity: all repo methods were invoked at least once
    invoked = {name for (name, *_rest) in repo.calls}
    assert {"list", "count", "get", "create", "update", "delete", "search", "count_filtered", "exists"} <= invoked

