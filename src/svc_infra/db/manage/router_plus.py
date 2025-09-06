from __future__ import annotations

from typing import Any, Optional, Sequence, Type, cast
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, Body

from .http import LimitOffsetParams, OrderParams, Page, SearchParams, build_order_by
from .service import Service


def make_crud_router_plus(
        *,
        model: Type[Any],
        service: Service,
        read_schema: Type[Any],
        create_schema: Type[Any],
        update_schema: Type[Any],
        prefix: str,
        tags: list[str] | None = None,
        search_fields: Optional[Sequence[str]] = None,
        default_ordering: Optional[str] = None,
        allowed_order_fields: Optional[list[str]] = None,
        session_dep: Any,
        mount_under_db_prefix: bool = True,
) -> APIRouter:
    router_prefix = ("/_db" + prefix) if mount_under_db_prefix else prefix
    r = APIRouter(prefix=router_prefix, tags=tags or [prefix.strip("/")])

    def _parse_ordering_to_fields(order_spec: Optional[str]) -> list[str]:
        if not order_spec:
            return []
        pieces = [p.strip() for p in order_spec.split(",") if p.strip()]
        fields: list[str] = []
        for p in pieces:
            name = p[1:] if p.startswith("-") else p
            if allowed_order_fields and name not in allowed_order_fields:
                continue  # silently ignore disallowed
            fields.append(p)
        return fields

    # LIST (with pagination, ordering, search)
    @r.get("/", response_model=cast(Any, Page[read_schema]))  # type: ignore[valid-type]
    async def list_items(
            lp: LimitOffsetParams = Depends(),
            op: OrderParams = Depends(),
            sp: SearchParams = Depends(),
            session=Depends(session_dep),
    ):
        order_spec = op.order_by or default_ordering
        order_fields = _parse_ordering_to_fields(order_spec)
        order_by = build_order_by(model, order_fields)

        if sp.q:
            fields = [f.strip() for f in (sp.fields or (",".join(search_fields or []) or "")).split(",") if f.strip()]
            items = await service.search(session, q=sp.q, fields=fields, limit=lp.limit, offset=lp.offset, order_by=order_by)
            total = await service.count_filtered(session, q=sp.q, fields=fields)
        else:
            items = await service.list(session, limit=lp.limit, offset=lp.offset, order_by=order_by)
            total = await service.count(session)

        return Page[read_schema].from_items(total=total, items=items, limit=lp.limit, offset=lp.offset)  # type: ignore[valid-type]

    # GET
    @r.get("/{item_id}", response_model=cast(Any, read_schema))
    async def get_item(item_id: Any, session=Depends(session_dep)):
        row = await service.get(session, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # CREATE
    @r.post("/", response_model=cast(Any, read_schema), status_code=201)
    async def create_item(payload: dict = Body(...), session=Depends(session_dep)):  # accept raw dict body
        try:
            data = create_schema.model_validate(payload).model_dump(exclude_unset=True)
            return await service.create(session, data)
        except IntegrityError as e:
            raise HTTPException(status_code=409, detail="Constraint violation") from e

    # UPDATE
    @r.patch("/{item_id}", response_model=cast(Any, read_schema))
    async def update_item(item_id: Any, payload: dict = Body(...), session=Depends(session_dep)):
        try:
            data = update_schema.model_validate(payload).model_dump(exclude_unset=True)
            row = await service.update(session, item_id, data)
        except IntegrityError as e:
            raise HTTPException(status_code=409, detail="Constraint violation") from e
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # DELETE (hard or soft depending on repo config)
    @r.delete("/{item_id}", status_code=204)
    async def delete_item(item_id: Any, session=Depends(session_dep)):
        ok = await service.delete(session, item_id)
        if not ok:
            raise HTTPException(404, "Not found")
        return

    return r