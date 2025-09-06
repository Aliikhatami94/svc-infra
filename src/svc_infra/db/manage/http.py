from __future__ import annotations

from typing import Generic, Iterable, List, Optional, Sequence, TypeVar, Any
from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class LimitOffsetParams(BaseModel):
    limit: int = Query(50, ge=1, le=1000)
    offset: int = Query(0, ge=0)


class OrderParams(BaseModel):
    # comma-separated, e.g. "-created_at,name"
    order_by: Optional[str] = Query(None, description="Comma-separated fields; prefix with '-' for DESC")


class SearchParams(BaseModel):
    # free text query
    q: Optional[str] = Query(None, description="Search query")
    # restrict to fields if provided (else router chooses sensible defaults)
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to search")


class Page(BaseModel, Generic[T]):
    total: int
    items: List[T]
    limit: int
    offset: int

    @classmethod
    def from_items(
            cls,
            *,
            total: int,
            items: Sequence[T] | Iterable[T],
            limit: int,
            offset: int,
    ) -> "Page[T]":
        return cls(total=total, items=list(items), limit=limit, offset=offset)


# Utility used by tests and router to build SQLAlchemy order_by list from field specs

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
