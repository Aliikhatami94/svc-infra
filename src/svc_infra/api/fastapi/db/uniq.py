from __future__ import annotations

from typing import Iterable, Optional, Dict, Any, Callable
from sqlalchemy import func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .repository import Repository
from svc_infra.db.uniq import ColumnSpec, _as_tuple

def make_uniqueness_hooks(
        *,
        model: type,
        repo: Repository,
        unique_cs: Iterable[ColumnSpec] = (),
        unique_ci: Iterable[ColumnSpec] = (),
        tenant_field: Optional[str] = None,
        duplicate_message: str = "Duplicate resource violates uniqueness policy.",
) -> tuple[
    Callable[[Dict[str, Any]], Any],  # async pre_create(data) -> data
    Callable[[Dict[str, Any]], Any],  # async pre_update(data) -> data
]:
    """Return (pre_create, pre_update) hooks that check duplicates *before* insert/update.

    Usage with ServiceWithHooks:
        pre_c, pre_u = make_uniqueness_hooks(model=User, repo=repo, unique_ci=["email"], tenant_field="tenant_id")
        svc = ServiceWithHooks(repo, pre_create=pre_c, pre_update=pre_u)
    """
    cs_specs = [_as_tuple(s) for s in unique_cs]
    ci_specs = [_as_tuple(s) for s in unique_ci]

    def _build_wheres(data: Dict[str, Any]):
        wheres = []

        def col(name: str):
            return getattr(model, name)

        tenant_val = data.get(tenant_field) if tenant_field else None

        # case-sensitive groups
        for spec in cs_specs:
            if not all(k in data for k in spec):
                continue
            parts = []
            if tenant_field:
                parts.append(col(tenant_field).is_(None) if tenant_val is None else col(tenant_field) == tenant_val)
            for k in spec:
                parts.append(col(k) == data[k])
            wheres.append(and_(*parts))

        # case-insensitive groups
        for spec in ci_specs:
            if not all(k in data for k in spec):
                continue
            parts = []
            if tenant_field:
                parts.append(col(tenant_field).is_(None) if tenant_val is None else col(tenant_field) == tenant_val)
            for k in spec:
                # compare lower(db_col) == lower(<value>) safely
                parts.append(func.lower(col(k)) == func.lower(func.cast(data[k], col(k).type)))
            wheres.append(and_(*parts))

        return wheres

    async def _deferred_check(session: AsyncSession, data: Dict[str, Any]):
        wheres = _build_wheres(data)
        for where in wheres:
            if await repo.exists(session, where=[where]):
                from fastapi import HTTPException
                raise HTTPException(status_code=409, detail=duplicate_message)

    async def _pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
        # store a coroutine to be awaited when a session is available in Service.create
        data = dict(data)
        data.setdefault("__uniq_check__", _deferred_check)
        return data

    async def _pre_update(data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        data.setdefault("__uniq_check__", _deferred_check)
        return data

    return _pre_create, _pre_update