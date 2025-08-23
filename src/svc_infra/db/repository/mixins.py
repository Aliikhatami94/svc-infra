from __future__ import annotations

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
        res = await self.session.execute(type(self).model.__table__.delete().where(cond))  # type: ignore[attr-defined]
        return int(res.rowcount or 0)

