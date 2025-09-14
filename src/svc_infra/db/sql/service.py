from __future__ import annotations

from typing import Any, Sequence

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from svc_infra.db.sql.repository import SqlRepository


class SqlService:
    """
    Small orchestration layer. Extend/override for business logic, RBAC, etc.
    """

    def __init__(self, repo: SqlRepository):
        self.repo = repo

    # hooks — override in subclasses if needed
    async def pre_create(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    async def pre_update(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    async def list(self, session: AsyncSession, *, limit: int, offset: int, order_by=None):
        return await self.repo.list(session, limit=limit, offset=offset, order_by=order_by)

    async def count(self, session: AsyncSession) -> int:
        return await self.repo.count(session)

    async def get(self, session: AsyncSession, id_value: Any):
        return await self.repo.get(session, id_value)

    async def create(self, session: AsyncSession, data: dict[str, Any]):
        data = await self.pre_create(data)
        try:
            return await self.repo.create(session, data)
        except IntegrityError as e:
            # unique constraint or not-null -> 409/400 instead of 500
            msg = str(e.orig) if getattr(e, "orig", None) else str(e)
            if "duplicate key value" in msg or "UniqueViolation" in msg:
                raise HTTPException(status_code=409, detail="Record already exists.") from e
            if "not-null" in msg or "NotNullViolation" in msg:
                raise HTTPException(status_code=400, detail="Missing required field.") from e
            raise  # unknown, let your error middleware turn into 500

    async def update(self, session: AsyncSession, id_value: Any, data: dict[str, Any]):
        data = await self.pre_update(data)
        return await self.repo.update(session, id_value, data)

    async def delete(self, session: AsyncSession, id_value: Any) -> bool:
        return await self.repo.delete(session, id_value)

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
            session, q=q, fields=fields, limit=limit, offset=offset, order_by=order_by
        )

    async def count_filtered(self, session: AsyncSession, *, q: str, fields: Sequence[str]) -> int:
        return await self.repo.count_filtered(session, q=q, fields=fields)

    async def exists(self, session: AsyncSession, *, where):
        return await self.repo.exists(session, where=where)
