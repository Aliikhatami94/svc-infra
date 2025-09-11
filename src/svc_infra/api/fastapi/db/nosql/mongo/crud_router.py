from __future__ import annotations

from typing import Annotated, Any, Optional, Sequence, Type, cast

from fastapi import APIRouter, Body, Depends, HTTPException

from svc_infra.api.fastapi.db.http import (
    LimitOffsetParams,
    OrderParams,
    Page,
    SearchParams,
    dep_limit_offset,
    dep_order,
    dep_search,
)
from svc_infra.db.nosql.mongo.client import get_db
from svc_infra.db.nosql.repository import NoSqlRepository
from svc_infra.db.nosql.service import NoSqlService


def _parse_sort(
    order_spec: Optional[str], allowed_order_fields: Optional[list[str]]
) -> list[tuple[str, int]]:
    """
    Translate "name,-created_at" -> [("name", 1), ("created_at", -1)] and honor allowed fields.
    """
    if not order_spec:
        return []
    out: list[tuple[str, int]] = []
    for raw in [p.strip() for p in order_spec.split(",") if p.strip()]:
        field = raw[1:] if raw.startswith("-") else raw
        if allowed_order_fields and field not in allowed_order_fields:
            continue
        out.append((field, -1 if raw.startswith("-") else 1))
    return out


def make_crud_router_plus_mongo(
    *,
    collection: str,
    repo: NoSqlRepository,
    service: NoSqlService,
    read_schema: Type[Any],
    create_schema: Type[Any],
    update_schema: Type[Any],
    prefix: str,
    tags: list[str] | None = None,
    search_fields: Optional[Sequence[str]] = None,
    default_ordering: Optional[str] = None,
    allowed_order_fields: Optional[list[str]] = None,
    mount_under_db_prefix: bool = True,
) -> APIRouter:
    router_prefix = ("/_mongo" + prefix) if mount_under_db_prefix else prefix
    r = APIRouter(
        prefix=router_prefix,
        tags=tags or [prefix.strip("/")],
        redirect_slashes=False,
    )

    @r.get("", response_model=cast(Any, Page[read_schema]))
    @r.get("/", response_model=cast(Any, Page[read_schema]))
    async def list_items(
        lp: Annotated[LimitOffsetParams, Depends(dep_limit_offset)],
        op: Annotated[OrderParams, Depends(dep_order)],
        sp: Annotated[SearchParams, Depends(dep_search)],
    ):
        db = await get_db()
        order_spec = op.order_by or default_ordering
        sort = _parse_sort(order_spec, allowed_order_fields)

        if sp.q and search_fields:
            items = await service.search(
                db,
                q=sp.q,
                fields=search_fields,
                limit=lp.limit,
                offset=lp.offset,
                sort=sort,
            )
            total = await service.count_filtered(db, q=sp.q, fields=search_fields)
        else:
            items = await service.list(db, limit=lp.limit, offset=lp.offset, sort=sort)
            total = await service.count(db)

        return Page[read_schema].from_items(
            total=total, items=items, limit=lp.limit, offset=lp.offset
        )

    @r.get("/{item_id}", response_model=cast(Any, read_schema))
    async def get_item(item_id: Any):
        db = await get_db()
        row = await service.get(db, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    @r.post("", response_model=cast(Any, read_schema), status_code=201)
    @r.post("/", response_model=cast(Any, read_schema), status_code=201)
    async def create_item(payload: create_schema = Body(...)):
        db = await get_db()
        data = payload.model_dump(exclude_unset=True)
        return await service.create(db, data)

    @r.patch("/{item_id}", response_model=cast(Any, read_schema))
    async def update_item(item_id: Any, payload: update_schema = Body(...)):
        db = await get_db()
        data = payload.model_dump(exclude_unset=True)
        row = await service.update(db, item_id, data)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    @r.delete("/{item_id}", status_code=204)
    async def delete_item(item_id: Any):
        db = await get_db()
        ok = await service.delete(db, item_id)
        if not ok:
            raise HTTPException(404, "Not found")
        return

    return r
