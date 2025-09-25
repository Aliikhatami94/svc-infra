from typing import Annotated, Any, Optional, Sequence, Type, TypeVar, cast

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from svc_infra.api.fastapi import public_router
from svc_infra.api.fastapi.db.http import (
    LimitOffsetParams,
    OrderParams,
    Page,
    SearchParams,
    build_order_by,
    dep_limit_offset,
    dep_order,
    dep_search,
)
from svc_infra.db.sql.service import SqlService

from .session import SqlSessionDep

CreateModel = TypeVar("CreateModel", bound=BaseModel)
ReadModel = TypeVar("ReadModel", bound=BaseModel)
UpdateModel = TypeVar("UpdateModel", bound=BaseModel)


def make_crud_router_plus_sql(
    *,
    model: type[Any],
    service: SqlService,
    read_schema: Type[ReadModel],
    create_schema: Type[CreateModel],
    update_schema: Type[UpdateModel],
    prefix: str,
    tags: list[str] | None = None,
    search_fields: Optional[Sequence[str]] = None,
    default_ordering: Optional[str] = None,
    allowed_order_fields: Optional[list[str]] = None,
    mount_under_db_prefix: bool = True,
) -> APIRouter:
    router_prefix = ("/_sql" + prefix) if mount_under_db_prefix else prefix
    router = public_router(
        prefix=router_prefix,
        tags=tags or [prefix.strip("/")],
        redirect_slashes=False,
    )

    def _parse_ordering_to_fields(order_spec: Optional[str]) -> list[str]:
        if not order_spec:
            return []
        pieces = [p.strip() for p in order_spec.split(",") if p.strip()]
        fields: list[str] = []
        for p in pieces:
            name = p[1:] if p.startswith("-") else p
            if allowed_order_fields and name not in (allowed_order_fields or []):
                continue
            fields.append(p)
        return fields

    # -------- LIST --------
    @router.get("", response_model=cast(Any, Page[read_schema]))
    async def list_items(
        lp: Annotated[LimitOffsetParams, Depends(dep_limit_offset)],
        op: Annotated[OrderParams, Depends(dep_order)],
        sp: Annotated[SearchParams, Depends(dep_search)],
        session: SqlSessionDep,  # type: ignore[name-defined]
    ):
        order_spec = op.order_by or default_ordering
        order_fields = _parse_ordering_to_fields(order_spec)
        order_by = build_order_by(model, order_fields)

        if sp.q:
            fields = [
                f.strip()
                for f in (sp.fields or (",".join(search_fields or []) or "")).split(",")
                if f.strip()
            ]
            items = await service.search(
                session, q=sp.q, fields=fields, limit=lp.limit, offset=lp.offset, order_by=order_by
            )
            total = await service.count_filtered(session, q=sp.q, fields=fields)
        else:
            items = await service.list(session, limit=lp.limit, offset=lp.offset, order_by=order_by)
            total = await service.count(session)
        return Page[read_schema].from_items(
            total=total, items=items, limit=lp.limit, offset=lp.offset
        )

    # -------- GET by id --------
    @router.get("/{item_id}", response_model=cast(Any, read_schema))
    async def get_item(item_id: Any, session: SqlSessionDep):  # type: ignore[name-defined]
        row = await service.get(session, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # -------- CREATE --------
    @router.post("", response_model=cast(Any, read_schema), status_code=201)
    async def create_item(
        session: SqlSessionDep,  # type: ignore[name-defined]
        payload: create_schema = Body(...),
    ):
        data = cast(BaseModel, payload).model_dump(exclude_unset=True)
        return await service.create(session, data)

    # -------- UPDATE --------
    @router.patch("/{item_id}", response_model=cast(Any, read_schema))
    async def update_item(
        item_id: Any,
        session: SqlSessionDep,  # type: ignore[name-defined]
        payload: update_schema = Body(...),
    ):
        data = cast(BaseModel, payload).model_dump(exclude_unset=True)
        row = await service.update(session, item_id, data)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # -------- DELETE --------
    @router.delete("/{item_id}", status_code=204)
    async def delete_item(item_id: Any, session: SqlSessionDep):  # type: ignore[name-defined]
        ok = await service.delete(session, item_id)
        if not ok:
            raise HTTPException(404, "Not found")
        return

    return router


__all__ = ["make_crud_router_plus_sql"]
