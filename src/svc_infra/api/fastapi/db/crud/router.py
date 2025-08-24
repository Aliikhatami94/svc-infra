from typing import Any, Type
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from svc_infra.api.fastapi.db.integration import SessionDep

def make_crud_router(
        *,
        model: Type[Any],
        read_schema: Type[Any],
        create_schema: Type[Any],
        update_schema: Type[Any],
        prefix: str,
        tags: list[str] | None = None,
        id_attr: str = "id",
) -> APIRouter:
    router_prefix = "/_db" + prefix
    r = APIRouter(prefix=router_prefix, tags=tags or [prefix.strip("/")])

    @r.get("/", response_model=list[read_schema])
    async def list_items(session: SessionDep):
        rows = (await session.execute(select(model))).scalars().all()
        return rows

    @r.get("/{item_id}", response_model=read_schema)
    async def get_item(item_id: Any, session: SessionDep):
        row = await session.get(model, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    @r.post("/", response_model=read_schema, status_code=201)
    async def create_item(payload: create_schema, session: SessionDep):
        row = model(**payload.model_dump(exclude_unset=True))
        session.add(row)
        try:
            await session.flush()
        except IntegrityError as e:
            raise HTTPException(400, f"Integrity error: {e.orig}")
        return row

    @r.patch("/{item_id}", response_model=read_schema)
    async def update_item(item_id: Any, payload: update_schema, session: SessionDep):
        row = await session.get(model, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        await session.flush()
        return row

    @r.delete("/{item_id}", status_code=204)
    async def delete_item(item_id: Any, session: SessionDep):
        row = await session.get(model, item_id)
        if row:
            await session.delete(row)
        return

    return r