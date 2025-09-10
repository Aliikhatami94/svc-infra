from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Any, Optional, Sequence, Type, cast, Annotated

from .session import SessionDep
from .http import (
    LimitOffsetParams, OrderParams, SearchParams, Page, build_order_by,
    dep_limit_offset, dep_order, dep_search,
)
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
        mount_under_db_prefix: bool = True,
) -> APIRouter:
    router_prefix = ("/_db" + prefix) if mount_under_db_prefix else prefix
    r = APIRouter(
        prefix=router_prefix,
        tags=tags or [prefix.strip("/")],
        redirect_slashes=False,  # avoid 307 that can drop body in some clients
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

    @r.get("", response_model=cast(Any, Page[read_schema]))   # type: ignore[valid-type]
    @r.get("/", response_model=cast(Any, Page[read_schema]))  # type: ignore[valid-type]
    async def list_items(
            lp: Annotated[LimitOffsetParams, Depends(dep_limit_offset)],
            op: Annotated[OrderParams,       Depends(dep_order)],
            sp: Annotated[SearchParams,      Depends(dep_search)],
            session: SessionDep,   # type: ignore[name-defined]
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
                session,
                q=sp.q,
                fields=fields,
                limit=lp.limit,
                offset=lp.offset,
                order_by=order_by,
            )
            total = await service.count_filtered(session, q=sp.q, fields=fields)
        else:
            items = await service.list(session, limit=lp.limit, offset=lp.offset, order_by=order_by)
            total = await service.count(session)

        return Page[read_schema].from_items(  # type: ignore[valid-type]
            total=total, items=items, limit=lp.limit, offset=lp.offset
        )

    @r.get("/{item_id}", response_model=cast(Any, read_schema))
    async def get_item(
            item_id: Any,
            session: SessionDep,   # type: ignore[name-defined]
    ):
        row = await service.get(session, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # CREATE — body is explicit, and non-default (session) comes before default (payload=Body(...))
    @r.post("", response_model=cast(Any, read_schema), status_code=201)
    @r.post("/", response_model=cast(Any, read_schema), status_code=201)
    async def create_item(
            session: SessionDep,                      # type: ignore[name-defined]
            payload: create_schema = Body(...),       # type: ignore[name-defined]
    ):
        data = payload.model_dump(exclude_unset=True)
        return await service.create(session, data)

    # UPDATE
    @r.patch("/{item_id}", response_model=cast(Any, read_schema))
    async def update_item(
            item_id: Any,
            session: SessionDep,                      # type: ignore[name-defined]
            payload: update_schema = Body(...),       # type: ignore[name-defined]
    ):
        data = payload.model_dump(exclude_unset=True)
        row = await service.update(session, item_id, data)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    @r.delete("/{item_id}", status_code=204)
    async def delete_item(
            item_id: Any,
            session: SessionDep,   # type: ignore[name-defined]
    ):
        ok = await service.delete(session, item_id)
        if not ok:
            raise HTTPException(404, "Not found")
        return

    return r