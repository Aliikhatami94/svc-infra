from collections.abc import Callable, Sequence
from typing import Annotated, Any, TypeVar, cast

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

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
from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.db.sql.service import SqlService
from svc_infra.db.sql.tenant import TenantSqlService

from ...tenancy.context import TenantId
from .session import SqlSessionDep

CreateModel = TypeVar("CreateModel", bound=BaseModel)
ReadModel = TypeVar("ReadModel", bound=BaseModel)
UpdateModel = TypeVar("UpdateModel", bound=BaseModel)


def make_crud_router_plus_sql(
    *,
    model: type[Any],
    service: SqlService,
    read_schema: type[ReadModel],
    create_schema: type[CreateModel],
    update_schema: type[UpdateModel],
    prefix: str,
    tags: list[str] | None = None,
    search_fields: Sequence[str] | None = None,
    default_ordering: str | None = None,
    allowed_order_fields: list[str] | None = None,
    mount_under_db_prefix: bool = True,
) -> APIRouter:
    router_prefix = ("/_sql" + prefix) if mount_under_db_prefix else prefix
    router = public_router(
        prefix=router_prefix,
        tags=tags or [prefix.strip("/")],
        redirect_slashes=False,
    )

    def _coerce_id(v: Any) -> Any:
        """Best-effort coercion of path ids: cast digit-only strings to int.

        Keeps original type otherwise to avoid breaking non-integer IDs.
        """
        if isinstance(v, str) and v.isdigit():
            try:
                return int(v)
            except Exception:
                return v
        return v

    def _parse_ordering_to_fields(order_spec: str | None) -> list[str]:
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
    @router.get(
        "",
        response_model=Page[read_schema],  # type: ignore[valid-type]
        description=f"List items of type {model.__name__}",
    )
    async def list_items(
        lp: Annotated[LimitOffsetParams, Depends(dep_limit_offset)],
        op: Annotated[OrderParams, Depends(dep_order)],
        sp: Annotated[SearchParams, Depends(dep_search)],
        session: SqlSessionDep,
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
        return Page[Any].from_items(total=total, items=items, limit=lp.limit, offset=lp.offset)

    # -------- GET by id --------
    @router.get(
        "/{item_id}",
        response_model=read_schema,
        description=f"Get item of type {model.__name__}",
    )
    async def get_item(item_id: Any, session: SqlSessionDep):
        row = await service.get(session, _coerce_id(item_id))
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # -------- CREATE --------
    @router.post(
        "",
        response_model=read_schema,
        status_code=201,
        description=f"Create item of type {model.__name__}",
    )
    async def create_item(
        session: SqlSessionDep,
        payload: create_schema = Body(...),  # type: ignore[valid-type]
    ):
        if isinstance(payload, BaseModel):
            data = cast("BaseModel", payload).model_dump(exclude_unset=True)
        elif isinstance(payload, dict):
            data = payload
        else:
            raise HTTPException(422, "invalid_payload")
        return await service.create(session, data)

    # -------- UPDATE --------
    @router.patch(
        "/{item_id}",
        response_model=read_schema,
        description=f"Update item of type {model.__name__}",
    )
    async def update_item(
        item_id: Any,
        session: SqlSessionDep,
        payload: update_schema = Body(...),  # type: ignore[valid-type]
    ):
        if isinstance(payload, BaseModel):
            data = cast("BaseModel", payload).model_dump(exclude_unset=True)
        elif isinstance(payload, dict):
            data = payload
        else:
            raise HTTPException(422, "invalid_payload")
        row = await service.update(session, _coerce_id(item_id), data)
        if not row:
            raise HTTPException(404, "Not found")
        return row

    # -------- DELETE --------
    @router.delete(
        "/{item_id}",
        status_code=204,
        description=f"Delete item of type {model.__name__}",
    )
    async def delete_item(item_id: Any, session: SqlSessionDep):
        ok = await service.delete(session, _coerce_id(item_id))
        if not ok:
            raise HTTPException(404, "Not found")
        return

    return router


def make_tenant_crud_router_plus_sql(
    *,
    model: type[Any],
    service_factory: Callable[[], Any],  # factory that returns a SqlService (will be wrapped)
    read_schema: type[ReadModel],
    create_schema: type[CreateModel],
    update_schema: type[UpdateModel],
    prefix: str,
    tenant_field: str = "tenant_id",
    tags: list[str] | None = None,
    search_fields: Sequence[str] | None = None,
    default_ordering: str | None = None,
    allowed_order_fields: list[str] | None = None,
    mount_under_db_prefix: bool = True,
) -> APIRouter:
    """Like make_crud_router_plus_sql, but requires TenantId and scopes all operations."""
    router_prefix = ("/_sql" + prefix) if mount_under_db_prefix else prefix
    router = public_router(
        prefix=router_prefix,
        tags=tags or [prefix.strip("/")],
        redirect_slashes=False,
    )

    # Evaluate the base service once to preserve in-memory state across requests in tests/local.
    # Consumers may pass either an instance or a zero-arg factory function.
    try:
        _base_instance = service_factory() if callable(service_factory) else service_factory
    except TypeError:
        # If the callable requires args, assume it's already an instance
        _base_instance = service_factory

    def _coerce_id(v: Any) -> Any:
        """Best-effort coercion of path ids: cast digit-only strings to int.
        Keeps original type otherwise.
        """
        if isinstance(v, str) and v.isdigit():
            try:
                return int(v)
            except Exception:
                return v
        return v

    def _parse_ordering_to_fields(order_spec: str | None) -> list[str]:
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

    # create per-request service with tenant scoping
    async def _svc(session: SqlSessionDep, tenant_id: TenantId):
        repo_or_service = getattr(_base_instance, "repo", _base_instance)
        svc: Any = TenantSqlService(repo_or_service, tenant_id=tenant_id, tenant_field=tenant_field)
        return svc

    @router.get("", response_model=Page[read_schema])  # type: ignore[valid-type]
    async def list_items(
        lp: Annotated[LimitOffsetParams, Depends(dep_limit_offset)],
        op: Annotated[OrderParams, Depends(dep_order)],
        sp: Annotated[SearchParams, Depends(dep_search)],
        session: SqlSessionDep,
        tenant_id: TenantId,
    ):
        svc = await _svc(session, tenant_id)
        order_spec = op.order_by or default_ordering
        order_fields = _parse_ordering_to_fields(order_spec)
        order_by = build_order_by(model, order_fields)
        if sp.q:
            fields = [
                f.strip()
                for f in (sp.fields or (",".join(search_fields or []) or "")).split(",")
                if f.strip()
            ]
            items = await svc.search(
                session,
                q=sp.q,
                fields=fields,
                limit=lp.limit,
                offset=lp.offset,
                order_by=order_by,
            )
            total = await svc.count_filtered(session, q=sp.q, fields=fields)
        else:
            items = await svc.list(session, limit=lp.limit, offset=lp.offset, order_by=order_by)
            total = await svc.count(session)
        return Page[Any].from_items(total=total, items=items, limit=lp.limit, offset=lp.offset)

    @router.get("/{item_id}", response_model=read_schema)
    async def get_item(item_id: Any, session: SqlSessionDep, tenant_id: TenantId):
        svc = await _svc(session, tenant_id)
        obj = await svc.get(session, item_id)
        if not obj:
            raise HTTPException(404, "not_found")
        return obj

    @router.post("", response_model=read_schema, status_code=201)
    async def create_item(
        session: SqlSessionDep,
        tenant_id: TenantId,
        payload: create_schema = Body(...),  # type: ignore[valid-type]
    ):
        svc = await _svc(session, tenant_id)
        if isinstance(payload, BaseModel):
            data = cast("BaseModel", payload).model_dump(exclude_unset=True)
        elif isinstance(payload, dict):
            data = payload
        else:
            raise HTTPException(422, "invalid_payload")
        return await svc.create(session, data)

    @router.patch("/{item_id}", response_model=read_schema)
    async def update_item(
        item_id: Any,
        session: SqlSessionDep,
        tenant_id: TenantId,
        payload: update_schema = Body(...),  # type: ignore[valid-type]
    ):
        svc = await _svc(session, tenant_id)
        if isinstance(payload, BaseModel):
            data = cast("BaseModel", payload).model_dump(exclude_unset=True)
        elif isinstance(payload, dict):
            data = payload
        else:
            raise HTTPException(422, "invalid_payload")
        updated = await svc.update(session, item_id, data)
        if not updated:
            raise HTTPException(404, "not_found")
        return updated

    @router.delete("/{item_id}", status_code=204)
    async def delete_item(item_id: Any, session: SqlSessionDep, tenant_id: TenantId):
        svc = await _svc(session, tenant_id)
        ok = await svc.delete(session, _coerce_id(item_id))
        if not ok:
            raise HTTPException(404, "Not found")
        return

    return router


__all__ = ["make_crud_router_plus_sql", "make_tenant_crud_router_plus_sql"]
