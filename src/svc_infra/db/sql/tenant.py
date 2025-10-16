from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from .service import SqlService


class TenantSqlService(SqlService):
    """
    SQL service wrapper that automatically scopes operations to a tenant.

    - Adds a where filter (model.tenant_field == tenant_id) for list/get/update/delete/search/count.
    - On create, if the model has the tenant field and it's not set in data, injects tenant_id.
    """

    def __init__(self, repo, *, tenant_id: str, tenant_field: str = "tenant_id"):
        super().__init__(repo)
        self.tenant_id = tenant_id
        self.tenant_field = tenant_field

    def _where(self) -> Sequence[Any]:
        model = self.repo.model
        col = getattr(model, self.tenant_field, None)
        if col is None:
            return []
        return [col == self.tenant_id]

    async def list(self, session: AsyncSession, *, limit: int, offset: int, order_by=None):
        return await self.repo.list(
            session, limit=limit, offset=offset, order_by=order_by, where=self._where()
        )

    async def count(self, session: AsyncSession) -> int:
        return await self.repo.count(session, where=self._where())

    async def get(self, session: AsyncSession, id_value: Any):
        return await self.repo.get(session, id_value, where=self._where())

    async def create(self, session: AsyncSession, data: dict[str, Any]):
        data = await self.pre_create(data)
        # inject tenant_id if model supports it and value missing
        if self.tenant_field in self.repo._model_columns() and self.tenant_field not in data:
            data[self.tenant_field] = self.tenant_id
        return await self.repo.create(session, data)

    async def update(self, session: AsyncSession, id_value: Any, data: dict[str, Any]):
        data = await self.pre_update(data)
        return await self.repo.update(session, id_value, data, where=self._where())

    async def delete(self, session: AsyncSession, id_value: Any) -> bool:
        return await self.repo.delete(session, id_value, where=self._where())

    async def search(
        self,
        session: AsyncSession,
        *,
        q: str,
        fields: Sequence[str],
        limit: int,
        offset: int,
        order_by=None,
    ):
        return await self.repo.search(
            session,
            q=q,
            fields=fields,
            limit=limit,
            offset=offset,
            order_by=order_by,
            where=self._where(),
        )

    async def count_filtered(self, session: AsyncSession, *, q: str, fields: Sequence[str]) -> int:
        return await self.repo.count_filtered(session, q=q, fields=fields, where=self._where())


__all__ = ["TenantSqlService"]
