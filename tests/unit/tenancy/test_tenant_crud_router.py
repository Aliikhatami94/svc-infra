from __future__ import annotations

from typing import Any

import pytest

# Skip tests if FastAPI is not installed (optional dependency)
fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from svc_infra.api.fastapi.db.sql.crud_router import make_tenant_crud_router_plus_sql  # noqa: E402
from svc_infra.api.fastapi.db.sql.session import get_session  # noqa: E402


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
        if not where or not isinstance(where, list) or len(where) == 0:
            return None
        first = where[0]
        # Handle tuple format: ("tenant_id", value)
        if isinstance(first, tuple) and len(first) == 2:
            if first[0] in ("tenant", "tenant_id"):
                return first[1]
        # Handle SQLAlchemy BinaryExpression: Model.tenant_id == "t1"
        # These have .right attribute for the value
        if hasattr(first, "right") and hasattr(first.right, "value"):
            return first.right.value
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
        # Coerce string IDs to int for comparison
        if isinstance(id_value, str) and id_value.isdigit():
            id_value = int(id_value)
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
        # Coerce string IDs to int for comparison
        if isinstance(id_value, str) and id_value.isdigit():
            id_value = int(id_value)
        for r in self.data.get(tid, []):
            if r["id"] == id_value:
                r.update(data)
                return r
        return None

    async def delete(self, session, id_value, *, where=None):
        tid = self._tenant_from_where(where)
        # Coerce string IDs to int for comparison
        if isinstance(id_value, str) and id_value.isdigit():
            id_value = int(id_value)
        rows = self.data.get(tid, [])
        for i, r in enumerate(rows):
            if r["id"] == id_value:
                del rows[i]
                return True
        return False

    async def search(self, session, *, q, fields, limit, offset, order_by=None, where=None):
        tid = self._tenant_from_where(where)
        rows = [r for r in self.data.get(tid, []) if q.lower() in r.get("name", "").lower()]
        return rows[offset : offset + limit]

    async def count_filtered(self, session, *, q, fields, where=None):
        tid = self._tenant_from_where(where)
        return len([r for r in self.data.get(tid, []) if q.lower() in r.get("name", "").lower()])


class _Create(BaseModel):
    name: str
    tenant_id: str | None = None


class _Update(BaseModel):
    name: str | None = None


class _Read(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    tenant_id: str | None = None


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
