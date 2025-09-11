from __future__ import annotations

from typing import Any, Sequence

from .repository import NoSqlRepository


class NoSqlService:
    """
    Small orchestration layer mirroring SqlService.
    """

    def __init__(self, repo: NoSqlRepository):
        self.repo = repo

    # hooks — override in subclasses if needed
    async def pre_create(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    async def pre_update(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    async def list(self, db, *, limit: int, offset: int, sort=None):
        return await self.repo.list(db, limit=limit, offset=offset, sort=sort)

    async def count(self, db) -> int:
        return await self.repo.count(db)

    async def get(self, db, id_value: Any):
        return await self.repo.get(db, id_value)

    async def create(self, db, data: dict[str, Any]):
        data = await self.pre_create(data)
        return await self.repo.create(db, data)

    async def update(self, db, id_value: Any, data: dict[str, Any]):
        data = await self.pre_update(data)
        return await self.repo.update(db, id_value, data)

    async def delete(self, db, id_value: Any) -> bool:
        return await self.repo.delete(db, id_value)

    async def search(
        self, db, *, q: str, fields: Sequence[str], limit: int, offset: int, sort=None
    ):
        return await self.repo.search(db, q=q, fields=fields, limit=limit, offset=offset, sort=sort)

    async def count_filtered(self, db, *, q: str, fields: Sequence[str]) -> int:
        return await self.repo.count_filtered(db, q=q, fields=fields)

    async def exists(self, db, *, where):
        return await self.repo.exists(db, where=where)
