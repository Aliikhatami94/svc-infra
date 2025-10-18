from __future__ import annotations

import base64
import contextvars
import json
from typing import Any, Callable, Generic, Iterable, List, Optional, Sequence, TypeVar

from fastapi import Query, Request
from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------- Core query models ----------
class CursorParams(BaseModel):
    cursor: Optional[str] = None
    limit: int = 50


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 50


class FilterParams(BaseModel):
    q: Optional[str] = None
    sort: Optional[str] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    updated_after: Optional[str] = None
    updated_before: Optional[str] = None


# ---------- Envelope model ----------
class Paginated(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: Optional[str] = Field(None, description="Opaque cursor for next page")
    total: Optional[int] = Field(None, description="Total items (optional)")


# ---------- Cursor helpers ----------
def _encode_cursor(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: Optional[str]) -> dict:
    """Public: decode an incoming cursor token for debugging/ops."""
    if not token:
        return {}
    s = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(s.encode("ascii")).decode("utf-8")
    return json.loads(raw)


# ---------- Context ----------
class PaginationContext(Generic[T]):
    envelope: bool
    allow_cursor: bool
    allow_page: bool

    cursor_params: CursorParams | None
    page_params: PageParams | None
    filters: FilterParams | None
    limit_override: int | None

    def __init__(
        self,
        *,
        envelope: bool,
        allow_cursor: bool,
        allow_page: bool,
        cursor_params: CursorParams | None,
        page_params: PageParams | None,
        filters: FilterParams | None,
        limit_override: int | None = None,
    ):
        self.envelope = envelope
        self.allow_cursor = allow_cursor
        self.allow_page = allow_page
        self.cursor_params = cursor_params
        self.page_params = page_params
        self.filters = filters
        self.limit_override = limit_override

    @property
    def cursor(self) -> Optional[str]:
        return (self.cursor_params or CursorParams()).cursor if self.allow_cursor else None

    @property
    def limit(self) -> int:
        # For cursor-based pagination, always honor the requested limit, even on the first page
        # (cursor may be None for the first page).
        if self.allow_cursor and self.cursor_params:
            return self.cursor_params.limit
        if self.allow_page and self.page_params:
            return self.limit_override or self.page_params.page_size
        return 50

    @property
    def page(self) -> Optional[int]:
        return self.page_params.page if (self.allow_page and self.page_params) else None

    @property
    def page_size(self) -> Optional[int]:
        return self.page_params.page_size if (self.allow_page and self.page_params) else None

    @property
    def offset(self) -> int:
        if self.cursor is None and self.allow_page and self.page and self.page_size:
            return (self.page - 1) * self.page_size
        return 0

    def wrap(
        self, items: list[T], *, next_cursor: Optional[str] = None, total: Optional[int] = None
    ):
        if self.envelope:
            return Paginated[T](items=items, next_cursor=next_cursor, total=total)
        return items

    def next_cursor_from_last(
        self, items: Sequence[T], *, key: Callable[[T], str | int]
    ) -> Optional[str]:
        if not items:
            return None
        last_key = key(items[-1])
        return _encode_cursor({"after": last_key})


_pagination_ctx: contextvars.ContextVar[PaginationContext] = contextvars.ContextVar(
    "pagination_ctx", default=None
)


def use_pagination() -> PaginationContext:
    ctx = _pagination_ctx.get()
    if ctx is None:
        # Safe defaults; if a route forgot to install the injector
        ctx = PaginationContext(
            envelope=False,
            allow_cursor=True,
            allow_page=False,
            cursor_params=CursorParams(),
            page_params=None,
            filters=None,
        )
    return ctx


# ---------- Utilities ----------
def text_filter(items: Iterable[T], q: Optional[str], *getters: Callable[[T], str]) -> list[T]:
    if not q:
        return list(items)
    ql = q.lower()
    out: list[T] = []
    for it in items:
        for g in getters:
            try:
                if ql in (g(it) or "").lower():
                    out.append(it)
                    break
            except Exception:
                pass
    return out


def sort_by(
    items: Iterable[T],
    *,
    key: Callable[[T], Any],
    desc: bool = False,
) -> list[T]:
    return sorted(list(items), key=key, reverse=desc)


def cursor_window(items, *, cursor, limit, key, descending: bool, offset: int = 0):
    # compute start_index
    if cursor:
        payload = decode_cursor(cursor)
        after = payload.get("after")
        ids = [key(x) for x in items]
        if descending:
            start_index = next((i for i, v in enumerate(ids) if v < after), len(items))
        else:
            start_index = next((i for i, v in enumerate(ids) if v > after), len(items))
    else:
        start_index = offset

    # take limit+1 to see if there’s another page
    slice_ = items[start_index : start_index + limit + 1]
    has_more = len(slice_) > limit
    window = slice_[:limit]

    next_cur = None
    if has_more and window:
        last_key = key(window[-1])
        next_cur = _encode_cursor({"after": last_key})

    return window, next_cur


# ---------- Dependency factories ----------
def make_pagination_injector(
    *,
    envelope: bool,
    allow_cursor: bool,
    allow_page: bool,
    default_limit: int = 50,
    max_limit: int = 200,
    include_filters: bool = False,
):
    """
    Returns a dependency with a signature that only includes the relevant query params.
    This keeps the generated OpenAPI in sync with actual behavior.
    """

    # Cursor-only (common case)
    if allow_cursor and not allow_page and not include_filters:

        async def _inject(
            request: Request,
            cursor: str | None = Query(None),
            limit: int = Query(default_limit, ge=1, le=max_limit),
        ):
            cur = CursorParams(cursor=cursor, limit=limit)
            _pagination_ctx.set(
                PaginationContext(
                    envelope=envelope,
                    allow_cursor=True,
                    allow_page=False,
                    cursor_params=cur,
                    page_params=None,
                    filters=None,
                )
            )
            return None

        return _inject

    # Cursor + filters
    if allow_cursor and not allow_page and include_filters:

        async def _inject(
            request: Request,
            cursor: str | None = Query(None),
            limit: int = Query(default_limit, ge=1, le=max_limit),
            q: str | None = Query(None),
            sort: str | None = Query(None),
            created_after: str | None = Query(None),
            created_before: str | None = Query(None),
            updated_after: str | None = Query(None),
            updated_before: str | None = Query(None),
        ):
            cur = CursorParams(cursor=cursor, limit=limit)
            flt = FilterParams(
                q=q,
                sort=sort,
                created_after=created_after,
                created_before=created_before,
                updated_after=updated_after,
                updated_before=updated_before,
            )
            _pagination_ctx.set(
                PaginationContext(
                    envelope=envelope,
                    allow_cursor=True,
                    allow_page=False,
                    cursor_params=cur,
                    page_params=None,
                    filters=flt,
                )
            )
            return None

        return _inject

    # Page-only
    if not allow_cursor and allow_page:

        async def _inject(
            request: Request,
            page: int = Query(1, ge=1),
            page_size: int = Query(default_limit, ge=1, le=max_limit),
        ):
            pag = PageParams(page=page, page_size=page_size)
            _pagination_ctx.set(
                PaginationContext(
                    envelope=envelope,
                    allow_cursor=False,
                    allow_page=True,
                    cursor_params=None,
                    page_params=pag,
                    filters=None,
                )
            )
            return None

        return _inject

    # Both cursor + page (rare; exposes all)
    async def _inject(
        request: Request,
        cursor: str | None = Query(None),
        limit: int = Query(default_limit, ge=1, le=max_limit),
        page: int = Query(1, ge=1),
        page_size: int = Query(default_limit, ge=1, le=max_limit),
        q: str | None = Query(None),
        sort: str | None = Query(None),
        created_after: str | None = Query(None),
        created_before: str | None = Query(None),
        updated_after: str | None = Query(None),
        updated_before: str | None = Query(None),
    ):
        cur = CursorParams(cursor=cursor, limit=limit) if allow_cursor else None
        pag = PageParams(page=page, page_size=page_size) if allow_page else None
        flt = (
            FilterParams(
                q=q,
                sort=sort,
                created_after=created_after,
                created_before=created_before,
                updated_after=updated_after,
                updated_before=updated_before,
            )
            if include_filters
            else None
        )

        _pagination_ctx.set(
            PaginationContext(
                envelope=envelope,
                allow_cursor=allow_cursor,
                allow_page=allow_page,
                cursor_params=cur,
                page_params=pag,
                filters=flt,
            )
        )
        return None

    return _inject


# ----- Convenience helpers for routers -----
def cursor_pager(
    default_limit: int = 50,
    max_limit: int = 200,
    *,
    envelope: bool = True,
    include_filters: bool = False,
):
    """
    The one-liner most routes should use.
    Produces OpenAPI with only: `cursor` and `limit` (plus filters if requested).
    """
    return make_pagination_injector(
        envelope=envelope,
        allow_cursor=True,
        allow_page=False,
        default_limit=default_limit,
        max_limit=max_limit,
        include_filters=include_filters,
    )
