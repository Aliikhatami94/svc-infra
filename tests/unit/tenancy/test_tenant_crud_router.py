from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.db.sql.crud_router import make_tenant_crud_router_plus_sql
from svc_infra.api.fastapi.db.sql.session import get_session
from svc_infra.api.fastapi.tenancy.context import TenantId


class _TenantCol:
    def __eq__(self, other):
        return ("tenant", other)


class _FakeService:
    def __init__(self):
        # store by tenant_id -> list of rows
        self.data: dict[str, list[dict[str, Any]]] = {"t1": [], "t2": []}
        self._id = 1

    @property
    def repo(self):
        # expose repo-like attribute to be wrapped by TenantSqlService
        return self

    # repository-shape methods used by TenantSqlService
    def _model_columns(self):
        return {"id", "name", "tenant_id"}

    class _Model:
        # fake SQLAlchemy model + column comparator to carry tenant id via equality expression
        tenant_id = _TenantCol()

    model = _Model()

    @staticmethod
    def _tenant_from_where(where):
        if (
            where
            and isinstance(where, list)
            and isinstance(where[0], tuple)
            and where[0][0] == "tenant"
        ):
            return where[0][1]
        return None

    async def list(self, session, *, limit, offset, order_by=None, where=None):
        tid = self._tenant_from_where(where)
        rows = list(self.data.get(tid, []))
        return rows[offset : offset + limit]

    async def count(self, session, *, where=None):
        tid = self._tenant_from_where(where)
        return len(self.data.get(tid, []))

    async def get(self, session, id_value, *, where=None):
        tid = self._tenant_from_where(where)
        for r in self.data.get(tid, []):
            if r["id"] == id_value:
                return r
        return None

    async def create(self, session, data):
        tid = data.get("tenant_id")
        row = {"id": self._id, **data}
        self._id += 1
        self.data.setdefault(tid, []).append(row)
        return row

    async def update(self, session, id_value, data, *, where=None):
        tid = self._tenant_from_where(where)
        for r in self.data.get(tid, []):
            if r["id"] == id_value:
                r.update(data)
                return r
        return None

    async def delete(self, session, id_value, *, where=None):
        tid = self._tenant_from_where(where)
        rows = self.data.get(tid, [])
        for i, r in enumerate(rows):
            if r["id"] == id_value:
                rows.pop(i)
                return True
        return False

    async def search(self, session, *, q, fields, limit, offset, order_by=None, where=None):
        tid = self._tenant_from_where(where)
        rows = [r for r in self.data.get(tid, []) if q.lower() in r.get("name", "").lower()]
        return rows[offset : offset + limit]

    async def count_filtered(self, session, *, q, fields, where=None):
        tid = self._tenant_from_where(where)
        return len([r for r in self.data.get(tid, []) if q.lower() in r.get("name", "").lower()])


class _Create:
    def __init__(self, name: str, tenant_id: str | None = None):
        self.name = name
        self.tenant_id = tenant_id

    def model_dump(self, *, exclude_unset: bool = False) -> dict[str, Any]:
        return {
            "name": self.name,
            **({} if self.tenant_id is None else {"tenant_id": self.tenant_id}),
        }


class _Update:
    def __init__(self, name: str | None = None):
        self.name = name

    def model_dump(self, *, exclude_unset: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.name is not None:
            out["name"] = self.name
        return out


class _Read:
    def __init__(self, **data):
        self.__dict__.update(data)


def _service_factory():
    # returns an instance; router will wrap with TenantSqlService
    return _FakeService()


@pytest.fixture
def app():
    app = FastAPI()
    router = make_tenant_crud_router_plus_sql(
        model=dict,  # model type is not used by fake service
        service_factory=_service_factory,
        read_schema=_Read,  # only used for annotation/casting
        create_schema=_Create,
        update_schema=_Update,
        prefix="/items",
        search_fields=["name"],
        mount_under_db_prefix=False,
    )
    app.include_router(router)

    # override DB session dependency to avoid requiring real DB init
    async def _override_session():
        class _S:  # minimal dummy session
            pass

        yield _S()

    app.dependency_overrides[get_session] = _override_session
    return app


def _client_with_tenant(app, tenant_id: str):
    return TestClient(app, headers={"X-Tenant-Id": tenant_id})


def test_create_injects_tenant_and_scopes_list(app):
    c1 = _client_with_tenant(app, "t1")
    c2 = _client_with_tenant(app, "t2")

    r = c1.post("/items", json={"name": "A"})
    assert r.status_code == 201
    assert r.json()["tenant_id"] == "t1"

    r = c2.get("/items")
    assert r.status_code == 200
    assert r.json()["total"] == 0

    r = c1.get("/items")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "A"
    assert body["items"][0]["tenant_id"] == "t1"


def test_cross_tenant_access_is_404(app):
    c1 = _client_with_tenant(app, "t1")
    c2 = _client_with_tenant(app, "t2")

    r = c1.post("/items", json={"name": "A"})
    item_id = r.json()["id"]

    # Another tenant cannot fetch it
    r = c2.get(f"/items/{item_id}")
    assert r.status_code == 404

    # Owner tenant can update; cross-tenant cannot
    r_ok = c1.patch(f"/items/{item_id}", json={"name": "AA"})
    assert r_ok.status_code == 200
    assert r_ok.json()["name"] == "AA"

    r_no = c2.patch(f"/items/{item_id}", json={"name": "BB"})
    assert r_no.status_code == 404

    # Delete by owner ok, others 404
    r_del_no = c2.delete(f"/items/{item_id}")
    assert r_del_no.status_code == 404
    r_del_ok = c1.delete(f"/items/{item_id}")
    assert r_del_ok.status_code == 204
