from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from svc_infra.db.sql.repository import SqlRepository
from svc_infra.db.sql.service_with_hooks import SqlServiceWithHooks

from .uniq import _as_tuple

ColumnSpec = Union[str, Sequence[str]]


def _all_present(data: Dict[str, Any], fields: Sequence[str]) -> bool:
    return all(f in data for f in fields)


def _nice_label(fields: Sequence[str], data: Dict[str, Any]) -> str:
    if len(fields) == 1:
        f = fields[0]
        return f"{f}={data.get(f)!r}"
    return "(" + ", ".join(f"{f}={data.get(f)!r}" for f in fields) + ")"


def dedupe_sql_service(
    repo: SqlRepository,
    *,
    unique_cs: Iterable[ColumnSpec] = (),
    unique_ci: Iterable[ColumnSpec] = (),
    tenant_field: Optional[str] = None,
    messages: Optional[dict[Tuple[str, ...], str]] = None,
    pre_create: Optional[Callable[[dict], dict]] = None,
    pre_update: Optional[Callable[[dict], dict]] = None,
):
    """
    Build a Service subclass with uniqueness pre-checks:
      • Pre-create/update checks against given specs.
      • Default 409 messages like "Record with email='x' already exists."
      • Developer can override per-spec messages with `messages`.
    """
    Model = repo.model
    pk_attr = repo.id_attr or "id"
    messages = messages or {}

    def _build_where(
        spec: Tuple[str, ...], data: Dict[str, Any], *, ci: bool, exclude_id: Any | None
    ):
        clauses: List[Any] = []
        for col_name in spec:
            col = getattr(Model, col_name)
            val = data.get(col_name)

            # Handle NULLs explicitly; LOWER(NULL) is NULL and breaks equality semantics.
            if val is None:
                clauses.append(col.is_(None))
                continue

            if ci and isinstance(val, str):
                clauses.append(func.lower(col) == func.lower(val))
            else:
                clauses.append(col == val)

        if tenant_field and hasattr(Model, tenant_field):
            tcol = getattr(Model, tenant_field)
            tval = data.get(tenant_field)
            clauses.append(tcol.is_(None) if tval is None else tcol == tval)

        if exclude_id is not None and hasattr(Model, pk_attr):
            clauses.append(getattr(Model, pk_attr) != exclude_id)

        return clauses

    async def _precheck(session, data: Dict[str, Any], *, exclude_id: Any | None) -> None:
        # Check CI specs first to catch the broadest conflicts, then CS.
        for ci, spec_list in ((True, unique_ci), (False, unique_cs)):
            for spec in spec_list:
                fields = _as_tuple(spec)
                needed = list(fields) + ([tenant_field] if tenant_field else [])
                if not _all_present(data, needed):
                    continue
                where = _build_where(fields, data, ci=ci, exclude_id=exclude_id)
                if await repo.exists(session, where=where):
                    msg = (
                        messages.get(fields)
                        or f"Record with {_nice_label(fields, data)} already exists."
                    )
                    raise HTTPException(status_code=409, detail=msg)

    class _Svc(SqlServiceWithHooks):
        async def create(self, session, data):
            data = await self.pre_create(data)
            await _precheck(session, data, exclude_id=None)
            try:
                return await self.repo.create(session, data)
            except IntegrityError as e:
                # Race fallback: let DB constraint be the last line of defense.
                raise HTTPException(status_code=409, detail="Record already exists.") from e

        async def update(self, session, id_value, data):
            data = await self.pre_update(data)
            await _precheck(session, data, exclude_id=id_value)
            try:
                return await self.repo.update(session, id_value, data)
            except IntegrityError as e:
                raise HTTPException(status_code=409, detail="Record already exists.") from e

    return _Svc(repo, pre_create=pre_create, pre_update=pre_update)
