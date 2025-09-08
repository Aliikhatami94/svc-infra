from __future__ import annotations

import pytest
import pytest_asyncio
from typing import Any, Sequence
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

from svc_infra.api.fastapi.db.crud_router import make_crud_router_plus


class _Col:
    def __init__(self, name: str):
        self.name = name

    def asc(self):
        return (self.name, "asc")

    def desc(self):
        return (self.name, "desc")


class DummyModel:
    id = _Col("id")
    name = _Col("name")
    created_at = _Col("created_at")


class ReadSchema(BaseModel):
    id: int
    name: str


class CreateSchema(BaseModel):
    name: str


class UpdateSchema(BaseModel):
    name: str | None = None


class StubService:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.store: dict[int, dict[str, Any]] = {1: {"id": 1, "name": "a"}}
        self.raise_on: dict[str, Exception] = {}

    async def list(self, session, *, limit: int, offset: int, order_by=None):
        self.calls.append(("list", {"limit": limit, "offset": offset, "order_by": order_by}))
        return list(self.store.values())

    async def count(self, session) -> int:
        self.calls.append(("count", {}))
        return len(self.store)

    async def search(self, session, *, q: str, fields: Sequence[str], limit: int, offset: int, order_by=None):
        self.calls.append(("search", {"q": q, "fields": list(fields), "limit": limit, "offset": offset, "order_by": order_by}))
        return [v for v in self.store.values() if q.lower() in v["name"].lower()]

    async def count_filtered(self, session, *, q: str, fields: Sequence[str]) -> int:
        self.calls.append(("count_filtered", {"q": q, "fields": list(fields)}))
        return len([v for v in self.store.values() if q.lower() in v["name"].lower()])

    async def get(self, session, id_value: Any):
        self.calls.append(("get", {"id": id_value}))
        return self.store.get(int(id_value))

    async def create(self, session, data: dict[str, Any]):
        if ex := self.raise_on.get("create"):
            raise ex
        self.calls.append(("create", {"data": data}))
        new_id = max(self.store) + 1 if self.store else 1
        row = {"id": new_id, **data}
        self.store[new_id] = row
        return row

    async def update(self, session, id_value: Any, data: dict[str, Any]):
        if ex := self.raise_on.get("update"):
            raise ex
        self.calls.append(("update", {"id": id_value, "data": data}))
        if int(id_value) not in self.store:
            return None
        self.store[int(id_value)].update(data)
        return self.store[int(id_value)]

    async def delete(self, session, id_value: Any) -> bool:
        self.calls.append(("delete", {"id": id_value}))
        return self.store.pop(int(id_value), None) is not None


@pytest_asyncio.fixture()
async def app():
    svc = StubService()

    def session_dep():
        return object()

    router = make_crud_router_plus(
        model=DummyModel,
        service=svc,
        read_schema=ReadSchema,
        create_schema=CreateSchema,
        update_schema=UpdateSchema,
        prefix="/items",
        tags=["items"],
        search_fields=["name"],
        default_ordering="-created_at",
        allowed_order_fields=["created_at", "name"],
        session_dep=session_dep,
        mount_under_db_prefix=False,
    )

    app = FastAPI()
    app.include_router(router)
    app.state.stub_service = svc
    return app


@pytest.mark.asyncio
async def test_list_and_default_ordering(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # default ordering applied
        r = await client.get("/items/", params={"limit": 10, "offset": 0})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1 and data["items"][0]["id"] == 1

        # explicit order_by limited by allowed_order_fields
        r = await client.get("/items/", params={"limit": 10, "offset": 0, "order_by": "name"})
        assert r.status_code == 200
        svc: StubService = app.state.stub_service
        last_call = [c for c in svc.calls if c[0] == "list"][-1]
        assert ("name", "asc") in (last_call[1]["order_by"] or [])


@pytest.mark.asyncio
async def test_search_with_and_without_fields_param(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # default search_fields used
        r = await client.get("/items/", params={"limit": 10, "offset": 0, "q": "a"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1 and data["items"][0]["name"] == "a"

        # explicit fields override defaults
        r = await client.get("/items/", params={"limit": 10, "offset": 0, "q": "a", "fields": "name"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_create_update_delete_and_errors(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # get existing
        r = await client.get("/items/1")
        assert r.status_code == 200 and r.json()["id"] == 1

        # get missing
        r = await client.get("/items/999")
        assert r.status_code == 404

        # create ok
        r = await client.post("/items/", json={"name": "b"})
        assert r.status_code == 201 and r.json()["name"] == "b"

        # create integrity error -> 409
        app.state.stub_service.raise_on["create"] = IntegrityError("x", "y", "z")
        r = await client.post("/items/", json={"name": "dup"})
        assert r.status_code == 409
        app.state.stub_service.raise_on.pop("create", None)

        # update ok
        r = await client.patch("/items/1", json={"name": "aa"})
        assert r.status_code == 200 and r.json()["name"] == "aa"

        # update missing -> 404
        r = await client.patch("/items/999", json={"name": "x"})
        assert r.status_code == 404

        # update integrity error -> 409
        app.state.stub_service.raise_on["update"] = IntegrityError("x", "y", "z")
        r = await client.patch("/items/1", json={"name": "xx"})
        assert r.status_code == 409
        app.state.stub_service.raise_on.pop("update", None)

        # delete ok -> 204
        r = await client.delete("/items/1")
        assert r.status_code == 204

        # delete missing -> 404
        r = await client.delete("/items/999")
        assert r.status_code == 404
