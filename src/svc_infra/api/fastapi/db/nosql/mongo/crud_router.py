from typing import Annotated, Any, Optional, Sequence, Type, cast

from fastapi import APIRouter, Body, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from svc_infra.api.fastapi.db.http import (
    LimitOffsetParams,
    OrderParams,
    Page,
    SearchParams,
    dep_limit_offset,
    dep_order,
    dep_search,
)
from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.db.nosql.mongo.client import acquire_db
from svc_infra.db.nosql.service import NoSqlService

DBDep = Annotated[AsyncIOMotorDatabase, Depends(acquire_db)]


def _parse_sort(
    order_spec: Optional[str], allowed_order_fields: Optional[list[str]]
) -> list[tuple[str, int]]:
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
    router = public_router(
        prefix=router_prefix,
        tags=tags or [prefix.strip("/")],
        redirect_slashes=False,
    )

    # LIST
    @router.get(
        "",
        response_model=cast(Any, Page[read_schema]),
        description=f"List items in {prefix} collection",
    )
    async def list_items(
        db: DBDep,
        lp: Annotated[LimitOffsetParams, Depends(dep_limit_offset)],
        op: Annotated[OrderParams, Depends(dep_order)],
        sp: Annotated[SearchParams, Depends(dep_search)],
    ):
        sort = _parse_sort(op.order_by or default_ordering, allowed_order_fields)
        if sp.q and search_fields:
            items = await service.search(
                db, q=sp.q, fields=search_fields, limit=lp.limit, offset=lp.offset, sort=sort
            )
            total = await service.count_filtered(db, q=sp.q, fields=search_fields)
        else:
            items = await service.list(db, limit=lp.limit, offset=lp.offset, sort=sort)
            total = await service.count(db)
        return Page[read_schema].from_items(
            total=total, items=items, limit=lp.limit, offset=lp.offset
        )

    # GET by id
    @router.get(
        "/{item_id}",
        response_model=cast(Any, read_schema),
        description=f"Get item from {prefix} collection",
    )
    async def get_item(db: DBDep, item_id: Any):
        row = await service.get(db, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # CREATE
    @router.post(
        "",
        response_model=cast(Any, read_schema),
        status_code=201,
        description=f"Create item in {prefix} collection",
    )
    async def create_item(db: DBDep, payload: create_schema = Body(...)):
        data = payload.model_dump(exclude_unset=True)
        return await service.create(db, data)

    # UPDATE
    @router.patch(
        "/{item_id}",
        response_model=cast(Any, read_schema),
        description=f"Update item in {prefix} collection",
    )
    async def update_item(db: DBDep, item_id: Any, payload: update_schema = Body(...)):
        data = payload.model_dump(exclude_unset=True)
        row = await service.update(db, item_id, data)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # DELETE
    @router.delete(
        "/{item_id}",
        status_code=204,
        description=f"Delete item from {prefix} collection",
    )
    async def delete_item(db: DBDep, item_id: Any):
        ok = await service.delete(db, item_id)
        if not ok:
            raise HTTPException(404, "Not found")
        return

    return router
