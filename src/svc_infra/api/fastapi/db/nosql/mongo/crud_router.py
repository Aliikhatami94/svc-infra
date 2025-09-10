from __future__ import annotations

from typing import Annotated, Any, Optional, Sequence, Type, cast

from fastapi import APIRouter, Body, Depends, HTTPException

from svc_infra.api.fastapi.db.http import (
    LimitOffsetParams,
    Page,
    SearchParams,
    dep_limit_offset,
    dep_search,
)
from svc_infra.db.nosql.repository import NoSqlRepository

from .client import get_db


def make_mongo_crud_router(
    *,
    collection: str,
    repo: NoSqlRepository,
    read_schema: Type[Any],
    create_schema: Type[Any],
    update_schema: Type[Any],
    prefix: str,
    tags: list[str] | None = None,
    search_fields: Optional[Sequence[str]] = None,
    mount_under_prefix: bool = True,
) -> APIRouter:
    router_prefix = ("/_mongo" + prefix) if mount_under_prefix else prefix
    r = APIRouter(
        prefix=router_prefix,
        tags=tags or [prefix.strip("/")],
        redirect_slashes=False,
    )

    @r.get("", response_model=cast(Any, Page[read_schema]))
    @r.get("/", response_model=cast(Any, Page[read_schema]))
    async def list_items(
        lp: Annotated[LimitOffsetParams, Depends(dep_limit_offset)],
        sp: Annotated[SearchParams, Depends(dep_search)],
    ):
        db = await get_db()
        if sp.q and search_fields:
            items = await repo.search(
                db, q=sp.q, fields=search_fields, limit=lp.limit, offset=lp.offset
            )
            total = await repo.count(
                db,
                filter={"$or": [{f: {"$regex": sp.q, "$options": "i"}} for f in search_fields]},
            )
        else:
            items = await repo.list(db, limit=lp.limit, offset=lp.offset)
            total = await repo.count(db)
        return Page[read_schema].from_items(
            total=total, items=items, limit=lp.limit, offset=lp.offset
        )

    @r.get("/{item_id}", response_model=cast(Any, read_schema))
    async def get_item(item_id: Any):
        db = await get_db()
        row = await repo.get(db, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    @r.post("", response_model=cast(Any, read_schema), status_code=201)
    @r.post("/", response_model=cast(Any, read_schema), status_code=201)
    async def create_item(payload: create_schema = Body(...)):
        db = await get_db()
        data = payload.model_dump(exclude_unset=True)
        return await repo.create(db, data)

    @r.patch("/{item_id}", response_model=cast(Any, read_schema))
    async def update_item(item_id: Any, payload: update_schema = Body(...)):
        db = await get_db()
        data = payload.model_dump(exclude_unset=True)
        row = await repo.update(db, item_id, data)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    @r.delete("/{item_id}", status_code=204)
    async def delete_item(item_id: Any):
        db = await get_db()
        ok = await repo.delete(db, item_id)
        if not ok:
            raise HTTPException(404, "Not found")
        return

    return r
