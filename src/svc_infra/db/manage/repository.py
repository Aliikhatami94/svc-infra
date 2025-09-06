from __future__ import annotations

from typing import Any, Optional, Sequence, Iterable

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute


class Repository:
    """
    Very small async repository around a mapped SQLAlchemy model.
    """

    def __init__(self, *, model: type[Any], id_attr: str = "id", soft_delete: bool = False, soft_delete_field: str = "deleted_at"):
        self.model = model
        self.id_attr = id_attr
        self.soft_delete = soft_delete
        self.soft_delete_field = soft_delete_field

    def _id_column(self) -> InstrumentedAttribute:
        return getattr(self.model, self.id_attr)

    def _base_select(self) -> Select:
        stmt = select(self.model)
        if self.soft_delete and hasattr(self.model, self.soft_delete_field):
            stmt = stmt.where(getattr(self.model, self.soft_delete_field).is_(None))
        return stmt

    # basic ops

    async def list(self, session: AsyncSession, *, limit: int, offset: int, order_by: Optional[Sequence[Any]] = None) -> Sequence[Any]:
        stmt = self._base_select().limit(limit).offset(offset)
        if order_by:
            stmt = stmt.order_by(*order_by)
        rows = (await session.execute(stmt)).scalars().all()
        return rows

    async def count(self, session: AsyncSession) -> int:
        stmt = select(func.count()).select_from(self._base_select().subquery())
        return (await session.execute(stmt)).scalar_one()

    async def get(self, session: AsyncSession, id_value: Any) -> Any | None:
        # honors soft-delete if configured
        stmt = self._base_select().where(self._id_column() == id_value)
        return (await session.execute(stmt)).scalars().first()

    async def create(self, session: AsyncSession, data: dict[str, Any]) -> Any:
        obj = self.model(**data)
        session.add(obj)
        await session.flush()
        return obj

    async def update(self, session: AsyncSession, id_value: Any, data: dict[str, Any]) -> Any | None:
        obj = await self.get(session, id_value)
        if not obj:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await session.flush()
        return obj

    async def delete(self, session: AsyncSession, id_value: Any) -> bool:
        obj = await session.get(self.model, id_value)
        if not obj:
            return False
        if self.soft_delete and hasattr(self.model, self.soft_delete_field):
            setattr(obj, self.soft_delete_field, func.now())
            await session.flush()
            return True
        await session.delete(obj)
        return True

    async def search(
            self,
            session: AsyncSession,
            *,
            q: str,
            fields: Sequence[str],
            limit: int,
            offset: int,
            order_by: Optional[Sequence[Any]] = None,
    ) -> Sequence[Any]:
        ilike = f"%{q}%"
        conditions = []
        for f in fields:
            col = getattr(self.model, f, None)
            if col is not None:
                conditions.append(col.ilike(ilike))
        stmt = self._base_select()
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.limit(limit).offset(offset)
        if order_by:
            stmt = stmt.order_by(*order_by)
        return (await session.execute(stmt)).scalars().all()

    async def count_filtered(
            self,
            session: AsyncSession,
            *,
            q: str,
            fields: Sequence[str]
    ) -> int:
        ilike = f"%{q}%"
        conditions = []
        for f in fields:
            col = getattr(self.model, f, None)
            if col is not None:
                conditions.append(col.ilike(ilike))
        stmt = self._base_select()
        if conditions:
            stmt = stmt.where(and_(*conditions))
        # SELECT COUNT(*) FROM (<stmt>) as t
        return (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    async def exists(self, session: AsyncSession, *, where: Iterable[Any]) -> bool:
        stmt = self._base_select().where(and_(*where)).limit(1)
        return (await session.execute(stmt)).first() is not None