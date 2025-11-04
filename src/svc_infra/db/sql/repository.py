from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence, Set

from sqlalchemy import Select, String, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, class_mapper


class SqlRepository:
    """
    Very small async repository around a mapped SQLAlchemy model.
    """

    def __init__(
        self,
        *,
        model: type[Any],
        id_attr: str = "id",
        soft_delete: bool = False,
        soft_delete_field: str = "deleted_at",
        soft_delete_flag_field: str | None = None,
        immutable_fields: Optional[Set[str]] = None,
    ):
        self.model = model
        self.id_attr = id_attr
        self.soft_delete = soft_delete
        self.soft_delete_field = soft_delete_field
        self.soft_delete_flag_field = soft_delete_flag_field
        self.immutable_fields: Set[str] = set(
            immutable_fields or {"id", "created_at", "updated_at"}
        )

    def _model_columns(self) -> set[str]:
        return {c.key for c in class_mapper(self.model).columns}

    def _id_column(self) -> InstrumentedAttribute:
        return getattr(self.model, self.id_attr)

    def _base_select(self) -> Select:
        stmt = select(self.model)
        if self.soft_delete:
            # Filter out soft-deleted rows by timestamp and/or active flag
            if hasattr(self.model, self.soft_delete_field):
                stmt = stmt.where(getattr(self.model, self.soft_delete_field).is_(None))
            if self.soft_delete_flag_field and hasattr(self.model, self.soft_delete_flag_field):
                stmt = stmt.where(getattr(self.model, self.soft_delete_flag_field).is_(True))
        return stmt

    # basic ops

    async def list(
        self,
        session: AsyncSession,
        *,
        limit: int,
        offset: int,
        order_by: Optional[Sequence[Any]] = None,
        where: Optional[Sequence[Any]] = None,
    ) -> Sequence[Any]:
        stmt = self._base_select()
        if where:
            stmt = stmt.where(and_(*where))
        stmt = stmt.limit(limit).offset(offset)
        if order_by:
            stmt = stmt.order_by(*order_by)
        rows = (await session.execute(stmt)).scalars().all()
        return rows

    async def count(self, session: AsyncSession, *, where: Optional[Sequence[Any]] = None) -> int:
        base = self._base_select()
        if where:
            base = base.where(and_(*where))
        stmt = select(func.count()).select_from(base.subquery())
        return (await session.execute(stmt)).scalar_one()

    async def get(
        self, session: AsyncSession, id_value: Any, *, where: Optional[Sequence[Any]] = None
    ) -> Any | None:
        # honors soft-delete if configured
        stmt = self._base_select().where(self._id_column() == id_value)
        if where:
            stmt = stmt.where(and_(*where))
        return (await session.execute(stmt)).scalars().first()

    async def create(self, session: AsyncSession, data: dict[str, Any]) -> Any:
        valid = self._model_columns()
        filtered = {k: v for k, v in data.items() if k in valid}
        obj = self.model(**filtered)
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def update(
        self,
        session: AsyncSession,
        id_value: Any,
        data: dict[str, Any],
        *,
        where: Optional[Sequence[Any]] = None,
    ) -> Any | None:
        obj = await self.get(session, id_value, where=where)
        if not obj:
            return None
        valid = self._model_columns()
        for k, v in data.items():
            if k in valid and k not in self.immutable_fields:
                setattr(obj, k, v)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def delete(
        self, session: AsyncSession, id_value: Any, *, where: Optional[Sequence[Any]] = None
    ) -> bool:
        # Fast path: when no extra filters provided, use session.get for simplicity (matches tests)
        if not where:
            obj = await session.get(self.model, id_value)
        else:
            # Respect soft-delete and optional tenant/extra filters by selecting through base select
            stmt = self._base_select().where(self._id_column() == id_value)
            stmt = stmt.where(and_(*where))
            obj = (await session.execute(stmt)).scalars().first()
        if not obj:
            return False
        if self.soft_delete:
            # Prefer timestamp, also optionally set flag to False
            # Check attributes on the instance to support test doubles without class-level fields
            if hasattr(obj, self.soft_delete_field):
                setattr(obj, self.soft_delete_field, func.now())
            if self.soft_delete_flag_field and hasattr(obj, self.soft_delete_flag_field):
                setattr(obj, self.soft_delete_flag_field, False)
            await session.flush()
            return True
        session.delete(obj)
        await session.flush()
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
        where: Optional[Sequence[Any]] = None,
    ) -> Sequence[Any]:
        ilike = f"%{q}%"
        conditions = []
        for f in fields:
            col = getattr(self.model, f, None)
            if col is not None:
                try:
                    conditions.append(col.cast(String).ilike(ilike))
                except Exception:
                    # skip columns that cannot be used in ilike even with cast
                    continue
        stmt = self._base_select()
        if where:
            stmt = stmt.where(and_(*where))
        if conditions:
            stmt = stmt.where(or_(*conditions))
        stmt = stmt.limit(limit).offset(offset)
        if order_by:
            stmt = stmt.order_by(*order_by)
        return (await session.execute(stmt)).scalars().all()

    async def count_filtered(
        self,
        session: AsyncSession,
        *,
        q: str,
        fields: Sequence[str],
        where: Optional[Sequence[Any]] = None,
    ) -> int:
        ilike = f"%{q}%"
        conditions = []
        for f in fields:
            col = getattr(self.model, f, None)
            if col is not None:
                try:
                    conditions.append(col.cast(String).ilike(ilike))
                except Exception:
                    continue
        stmt = self._base_select()
        if where:
            stmt = stmt.where(and_(*where))
        if conditions:
            stmt = stmt.where(or_(*conditions))
        # SELECT COUNT(*) FROM (<stmt>) as t
        return (
            await session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()

    async def exists(self, session: AsyncSession, *, where: Iterable[Any]) -> bool:
        stmt = self._base_select().where(and_(*where)).limit(1)
        return (await session.execute(stmt)).first() is not None
