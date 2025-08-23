# Place pytest fixtures here if needed (optional)
from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, Type, TypeVar, cast

from sqlalchemy import delete, select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

T = TypeVar("T")


class Repository(Generic[T]):
    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    async def get(self, id: Any) -> Optional[T]:
        return await self.session.get(self.model, id)

    async def list(
        self,
        *,
        where: Optional[dict[str, Any]] = None,
        order_by: InstrumentedAttribute | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Sequence[T]:
        stmt = select(self.model)
        if where:
            stmt = stmt.where(and_(*[(cast(Any, getattr(self.model, k)) == v) for k, v in where.items()]))
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if limit:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)
        return (await self.session.execute(stmt)).scalars().all()

    async def count(self, where: Optional[dict[str, Any]] = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        if where:
            stmt = stmt.where(and_(*[(cast(Any, getattr(self.model, k)) == v) for k, v in where.items()]))
        return int((await self.session.execute(stmt)).scalar_one())

    async def create(self, **data) -> T:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def upsert(self, key_fields: dict[str, Any], **data) -> T:
        stmt = select(self.model).filter_by(**key_fields)
        obj = (await self.session.execute(stmt)).scalars().first()
        if obj is not None:
            for k, v in data.items():
                setattr(obj, k, v)
            await self.session.flush()
            return obj
        obj = self.model(**{**key_fields, **data})
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, id: Any, **data) -> Optional[T]:
        obj = await self.get(id)
        if obj is None:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await self.session.flush()
        return obj

    async def delete(self, id: Any) -> int:
        cond = cast(Any, self.model.id == id)
        res = await self.session.execute(delete(self.model).where(cond))
        return int(res.rowcount or 0)

