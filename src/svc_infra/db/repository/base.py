from __future__ import annotations

from typing import Any, AsyncIterator, Generic, Optional, Sequence, Type, TypeVar, cast

from sqlalchemy import delete, select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from .mixins import CRUDMixin

T = TypeVar("T")


class Repository(CRUDMixin[T], Generic[T]):
    """Generic async SQLAlchemy repository.

    - Exposes common CRUD helpers over an AsyncSession and SQLAlchemy model class.
    - Create/Update/Delete come from CRUDMixin to keep custom repos consistent.
    - This class provides get, list, count, and upsert helpers.
    """

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

