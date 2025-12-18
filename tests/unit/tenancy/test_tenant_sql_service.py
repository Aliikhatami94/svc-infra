from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from svc_infra.db.sql.repository import SqlRepository
from svc_infra.db.sql.tenant import TenantSqlService


class _Model:
    id = object()
    tenant_id = object()


class _Repo(SqlRepository):
    def __init__(self):
        super().__init__(model=_Model)
        # spy methods
        self._list = AsyncMock(return_value=[{"id": 1, "tenant_id": "t1"}])
        self._count = AsyncMock(return_value=1)
        self._get = AsyncMock(return_value={"id": 1, "tenant_id": "t1"})
        self._create = AsyncMock(side_effect=lambda s, d: d)
        self._update = AsyncMock(return_value={"id": 1, "tenant_id": "t1", "name": "n"})
        self._delete = AsyncMock(return_value=True)
        self._search = AsyncMock(return_value=[])
        self._count_filtered = AsyncMock(return_value=0)

    async def list(self, session, *, limit: int, offset: int, order_by=None, where=None):
        return await self._list(session, limit=limit, offset=offset, order_by=order_by, where=where)

    async def count(self, session, *, where=None):
        return await self._count(session, where=where)

    async def get(self, session, id_value, *, where=None):
        return await self._get(session, id_value, where=where)

    async def create(self, session, data):
        return await self._create(session, data)

    async def update(self, session, id_value, data, *, where=None):
        return await self._update(session, id_value, data, where=where)

    async def delete(self, session, id_value, *, where=None):
        return await self._delete(session, id_value, where=where)

    async def search(self, session, *, q, fields, limit, offset, order_by=None, where=None):
        return await self._search(
            session,
            q=q,
            fields=fields,
            limit=limit,
            offset=offset,
            order_by=order_by,
            where=where,
        )

    async def count_filtered(self, session, *, q, fields, where=None):
        return await self._count_filtered(session, q=q, fields=fields, where=where)

    def _model_columns(self):
        return {"tenant_id"}


@pytest.mark.asyncio
async def test_tenant_service_injects_tenant_on_create():
    repo = _Repo()
    tsvc = TenantSqlService(repo, tenant_id="tA")
    session = Mock()
    data = {"name": "x"}
    out = await tsvc.create(session, data)

    assert out["tenant_id"] == "tA"
    repo._create.assert_awaited()


@pytest.mark.asyncio
async def test_tenant_service_scopes_where_filters():
    repo = _Repo()
    tsvc = TenantSqlService(repo, tenant_id="tB")
    session = Mock()

    await tsvc.list(session, limit=10, offset=0)
    await tsvc.count(session)
    await tsvc.get(session, 1)
    await tsvc.update(session, 1, {"name": "n"})
    await tsvc.delete(session, 1)
    await tsvc.search(session, q="q", fields=["name"], limit=10, offset=0)
    await tsvc.count_filtered(session, q="q", fields=["name"])

    # verify where passed with tenant filter present
    for mock in (
        repo._list,
        repo._count,
        repo._get,
        repo._update,
        repo._delete,
        repo._search,
        repo._count_filtered,
    ):
        assert mock.await_args.kwargs.get("where") is not None
