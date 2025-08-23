from __future__ import annotations

from sqlalchemy import and_
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


class CRUDMixin(Generic[T]):
    async def create(self, **data) -> T:  # type: ignore[override]
        obj = self.model(**data)  # type: ignore[attr-defined]
        self.session.add(obj)     # type: ignore[attr-defined]
        await self.session.flush()  # type: ignore[attr-defined]
        return obj

    async def update(self, id: Any, **data) -> Optional[T]:  # type: ignore[override]
        obj = await self.get(id)  # type: ignore[attr-defined]
        if obj is None:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await self.session.flush()  # type: ignore[attr-defined]
        return obj

    async def delete(self, id: Any) -> int:  # type: ignore[override]
        cond = self.model.id == id  # type: ignore[attr-defined]
        res = await self.session.execute(self.model.__table__.delete().where(cond))  # type: ignore[attr-defined]
        return int(res.rowcount or 0)

def apply_filters(stmt, model, where: dict[str, Any] | None):
    if not where:
        return stmt
    return stmt.where(and_(*[(getattr(model, k) == v) for k, v in where.items()]))