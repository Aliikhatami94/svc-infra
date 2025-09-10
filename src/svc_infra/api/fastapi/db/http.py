from __future__ import annotations

from typing import Any, Generic, Iterable, List, Optional, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class LimitOffsetParams(BaseModel):
    limit: int
    offset: int


def dep_limit_offset(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> LimitOffsetParams:
    return LimitOffsetParams(limit=limit, offset=offset)


class OrderParams(BaseModel):
    order_by: Optional[str] = None


def dep_order(
    order_by: Optional[str] = Query(None, description="Comma-separated fields; '-' for DESC"),
) -> OrderParams:
    return OrderParams(order_by=order_by)


class SearchParams(BaseModel):
    q: Optional[str] = None
    fields: Optional[str] = None


def dep_search(
    q: Optional[str] = Query(None, description="Search query"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields"),
) -> SearchParams:
    return SearchParams(q=q, fields=fields)


class Page(BaseModel, Generic[T]):
    total: int
    items: List[T]
    limit: int
    offset: int

    @classmethod
    def from_items(
        cls, *, total: int, items: Sequence[T] | Iterable[T], limit: int, offset: int
    ) -> "Page[T]":
        return cls(total=total, items=list(items), limit=limit, offset=offset)


def build_order_by(model: Any, fields: Sequence[str]) -> list[Any]:
    """Translate ["-created_at", "name"] to [desc(Model.created_at), asc(Model.name)].

    Unknown fields are ignored. The model's attribute should expose .asc()/.desc() methods
    (as SQLAlchemy columns do). This function is intentionally tolerant for test doubles.
    """
    order_by: list[Any] = []
    for f in fields:
        if not f:
            continue
        direction = "desc" if f.startswith("-") else "asc"
        name = f[1:] if f.startswith("-") else f
        col = getattr(model, name, None)
        if col is None:
            continue
        # In tests, columns expose asc()/desc() returning simple tuples; in SQLA they return ClauseElement
        if direction == "desc" and hasattr(col, "desc"):
            order_by.append(col.desc())
        elif direction == "asc" and hasattr(col, "asc"):
            order_by.append(col.asc())
    return order_by
