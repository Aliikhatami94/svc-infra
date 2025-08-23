from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, Type, TypeVar
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .mixins import CRUDMixin, apply_filters

T = TypeVar("T")


@dataclass
class Page:
    items: Sequence[Any]
    total: int
    limit: int
    offset: int

async def paginate(session, stmt, *, limit: int = 50, offset: int = 0) -> Page:
    from sqlalchemy import func, select
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    items = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return Page(items=items, total=int(total or 0), limit=limit, offset=offset)

class Repository(CRUDMixin[T], Generic[T]):
    """Generic async SQLAlchemy repository.

    - Exposes common CRUD helpers over an AsyncSession and SQLAlchemy model class.
    - Create/Update/Delete come from CRUDMixin to keep custom repos consistent.
    - This class provides get, list, count, and upsert helpers.
    """

    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    def _base_select(self, *, include_deleted: bool = False):
        stmt = select(self.model)
        if hasattr(self.model, "is_deleted") and not include_deleted:
            stmt = stmt.where(self.model.is_deleted.is_(False))
        return stmt

    async def get(self, id: Any, *, include_deleted: bool = False) -> Optional[T]:
        stmt = apply_filters(self._base_select(include_deleted=include_deleted), self.model, {"id": id})
        return (await self.session.execute(stmt)).scalars().first()

    async def list(
        self,
        *,
        where: Optional[dict[str, Any]] = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
    ) -> Sequence[T]:
        stmt = apply_filters(self._base_select(include_deleted=include_deleted), self.model, where)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if limit:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)
        return (await self.session.execute(stmt)).scalars().all()

    async def count(self, where: Optional[dict[str, Any]] = None, *, include_deleted: bool = False) -> int:
        base_stmt = apply_filters(self._base_select(include_deleted=include_deleted), self.model, where)
        stmt = select(func.count()).select_from(base_stmt.subquery())
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
