from __future__ import annotations

from typing import Any, Iterable, List, Optional, Tuple, Type

from sqlalchemy import Index, func

from svc_infra.db.utils import KeySpec
from svc_infra.db.utils import as_tuple as _as_tuple


def make_unique_sql_indexes(
    model: Type[Any],
    *,
    unique_cs: Iterable[KeySpec] = (),
    unique_ci: Iterable[KeySpec] = (),
    tenant_field: Optional[str] = None,
    name_prefix: str = "uq",
) -> List[Index]:
    """Return SQLAlchemy Index objects that enforce uniqueness.

    - unique_cs: case-sensitive unique specs
    - unique_ci: case-insensitive unique specs (lower(column))
    - tenant_field: if provided, create two partial unique indexes:
        * tenant IS NULL (global bucket)
        * tenant IS NOT NULL (scoped per-tenant)

    Declare right after your model class; Alembic or metadata.create_all will pick them up.
    """
    idxs: List[Index] = []

    def _col(name: str):
        return getattr(model, name)

    def _to_sa_cols(spec: Tuple[str, ...], *, ci: bool):
        cols = []
        for cname in spec:
            c = _col(cname)
            cols.append(func.lower(c) if ci else c)
        return tuple(cols)

    tenant_col = _col(tenant_field) if tenant_field else None

    def _name(ci: bool, spec: Tuple[str, ...], null_bucket: Optional[str] = None):
        parts = [name_prefix, model.__tablename__]
        if tenant_field:
            parts.append(tenant_field)
        if null_bucket:
            parts.append(null_bucket)
        parts.append("ci" if ci else "cs")
        parts.extend(spec)
        return "_".join(parts)

    for ci, spec_list in ((False, unique_cs), (True, unique_ci)):
        for spec in spec_list:
            spec_t = _as_tuple(spec)
            cols = _to_sa_cols(spec_t, ci=ci)

            if tenant_col is None:
                idxs.append(Index(_name(ci, spec_t), *cols, unique=True))
            else:
                idxs.append(
                    Index(
                        _name(ci, spec_t, "null"),
                        *cols,
                        unique=True,
                        postgresql_where=tenant_col.is_(None),
                    )
                )
                idxs.append(
                    Index(
                        _name(ci, spec_t, "notnull"),
                        tenant_col,
                        *cols,
                        unique=True,
                        postgresql_where=tenant_col.isnot(None),
                    )
                )
    return idxs
