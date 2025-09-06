from __future__ import annotations

from typing import Generic, Iterable, List, Optional, Sequence, TypeVar
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