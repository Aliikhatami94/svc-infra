from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple

from fastapi import HTTPException

from svc_infra.db.utils import KeySpec
from svc_infra.db.utils import as_tuple as _as_tuple

from .repository import NoSqlRepository
from .service_with_hooks import NoSqlServiceWithHooks


def _all_present(data: Dict[str, Any], fields: Sequence[str]) -> bool:
    return all(f in data for f in fields)


def _nice_label(fields: Sequence[str], data: Dict[str, Any]) -> str:
    if len(fields) == 1:
        f = fields[0]
        return f"{f}={data.get(f)!r}"
    return "(" + ", ".join(f"{f}={data.get(f)!r}" for f in fields) + ")"


def _build_where(
    *,
    fields: Tuple[str, ...],
    data: Dict[str, Any],
    tenant_field: Optional[str],
    case_insensitive: bool,
    id_field: str,
    exclude_id: Any | None,
) -> Iterable[Dict[str, Any]]:
    conds = []
    for name in fields:
        val = data.get(name)
        if case_insensitive and isinstance(val, str):
            # $regex with ^...$ anchors for equality-like behavior (case-insensitive)
            conds.append({name: {"$regex": f"^{val}$", "$options": "i"}})
        else:
            conds.append({name: val})

    if tenant_field is not None:
        tval = data.get(tenant_field)
        conds.append({tenant_field: {"$exists": False}} if tval is None else {tenant_field: tval})

    if exclude_id is not None:
        conds.append({id_field: {"$ne": exclude_id}})

    return conds


def dedupe_nosql_service(
    repo: NoSqlRepository,
    *,
    unique_cs: Iterable[KeySpec] = (),
    unique_ci: Iterable[KeySpec] = (),
    tenant_field: Optional[str] = None,
    messages: Optional[dict[Tuple[str, ...], str]] = None,
    pre_create: Optional[Callable[[dict], dict]] = None,
    pre_update: Optional[Callable[[dict], dict]] = None,
):
    """
    Build a Service subclass with uniqueness pre-checks for Mongo:
      • Pre-create/update checks against given specs.
      • Default 409 with messages like "Record with email='x' already exists."
      • Per-spec message overrides via `messages`.
    """
    messages = messages or {}
    id_field = repo.id_field

    async def _precheck(db, data: Dict[str, Any], *, exclude_id: Any | None) -> None:
        for ci, spec_list in ((False, unique_cs), (True, unique_ci)):
            for spec in spec_list:
                fields = _as_tuple(spec)
                needed = list(fields) + ([tenant_field] if tenant_field else [])
                if not _all_present(data, needed):
                    continue
                where_parts = _build_where(
                    fields=fields,
                    data=data,
                    tenant_field=tenant_field,
                    case_insensitive=ci,
                    id_field=id_field,
                    exclude_id=exclude_id,
                )
                # repo.exists expects an iterable of dicts to AND together
                if await repo.exists(db, where=where_parts):
                    msg = (
                        messages.get(fields)
                        or f"Record with {_nice_label(fields, data)} already exists."
                    )
                    raise HTTPException(status_code=409, detail=msg)

    class _Svc(NoSqlServiceWithHooks):
        async def create(self, db, data):
            data = await self.pre_create(data)
            await _precheck(db, data, exclude_id=None)
            return await self.repo.create(db, data)

        async def update(self, db, id_value, data):
            data = await self.pre_update(data)
            await _precheck(db, data, exclude_id=id_value)
            return await self.repo.update(db, id_value, data)

    return _Svc(repo, pre_create=pre_create, pre_update=pre_update)
