from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from svc_infra.api.fastapi.db.repository import Repository
from svc_infra.api.fastapi.db.service_hooks import ServiceWithHooks

ColumnSpec = Union[str, Sequence[str]]  # "email" or ("first_name","last_name")

def _as_tuple(spec: ColumnSpec) -> Tuple[str, ...]:
    return (spec,) if isinstance(spec, str) else tuple(spec)

def _all_present(data: Dict[str, Any], fields: Sequence[str]) -> bool:
    return all(f in data for f in fields)

def _nice_label(fields: Sequence[str], data: Dict[str, Any]) -> str:
    # e.g. ("email",) -> email='a@b.com' ; ("first","last")-> (first='x', last='y')
    if len(fields) == 1:
        f = fields[0]
        return f"{f}={data.get(f)!r}"
    parts = [f"{f}={data.get(f)!r}" for f in fields]
    return "(" + ", ".join(parts) + ")"

def dedupe_service(
        repo: Repository,
        *,
        unique_cs: Iterable[ColumnSpec] = (),
        unique_ci: Iterable[ColumnSpec] = (),
        tenant_field: Optional[str] = None,
        # Optional: customize the error message per spec. Keys are tuples of column names.
        messages: Optional[dict[Tuple[str, ...], str]] = None,
):
    """
    Create a Service instance that:
      - Pre-checks duplicates for the provided uniqueness specs (case sensitive & insensitive)
      - Returns HTTP 409 with a friendly message
      - Still catches IntegrityError to 409 for race-safety
    The arguments mirror `make_unique_indexes(...)`.
    """
    Model = repo.model
    messages = messages or {}

    # Build a helper that turns a spec into a WHERE clause based on provided data
    def _build_where_from_spec(data: Dict[str, Any], spec: Tuple[str, ...], *, ci: bool, exclude_id: Any | None):
        clauses: List[Any] = []

        # spec columns
        for col_name in spec:
            col = getattr(Model, col_name)
            val = data.get(col_name)
            if ci:
                clauses.append(func.lower(col) == func.lower(val))
            else:
                clauses.append(col == val)

        # tenant scope (match your index semantics)
        if tenant_field and hasattr(Model, tenant_field):
            tcol = getattr(Model, tenant_field)
            tval = data.get(tenant_field)
            if tval is None:
                clauses.append(tcol.is_(None))
            else:
                clauses.append(tcol == tval)

        # exclude the current row on update
        if exclude_id is not None and hasattr(Model, "id"):
            clauses.append(getattr(Model, "id") != exclude_id)

        return clauses

    async def _precheck(session, data: Dict[str, Any], *, exclude_id: Any | None) -> None:
        # Check in deterministic order: CI specs, then CS specs
        for ci, spec_list in ((True, unique_ci), (False, unique_cs)):
            for spec in spec_list:
                fields = _as_tuple(spec)
                # only run if ALL fields (and tenant if used) are present in payload
                needed = list(fields) + ([tenant_field] if tenant_field else [])
                if not _all_present(data, needed):
                    continue
                where = _build_where_from_spec(data, fields, ci=ci, exclude_id=exclude_id)
                if await repo.exists(session, where=where):
                    msg = messages.get(fields) or f"Resource with {_nice_label(fields, data)} already exists."
                    raise HTTPException(status_code=409, detail=msg)

    class _Svc(ServiceWithHooks):
        async def create(self, session, data):
            data = await self.pre_create(data)
            # Run prechecks — exclude_id=None on create
            await _precheck(session, data, exclude_id=None)
            try:
                return await self.repo.create(session, data)
            except IntegrityError as e:
                # fall back to 409 for any of these uniqueness violations
                raise HTTPException(status_code=409, detail="Resource already exists.") from e

        async def update(self, session, id_value, data):
            data = await self.pre_update(data)
            # only run if payload contains some unique-relevant fields
            await _precheck(session, data, exclude_id=id_value)
            try:
                return await self.repo.update(session, id_value, data)
            except IntegrityError as e:
                raise HTTPException(status_code=409, detail="Resource already exists.") from e

    return _Svc(repo)