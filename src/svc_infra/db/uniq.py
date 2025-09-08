from __future__ import annotations
from typing import Iterable, Sequence, Tuple, Union, List, Optional
from sqlalchemy import Index, func


ColumnSpec = Union[str, Sequence[str]]  # "email" or ("first_name","last_name")


def _as_tuple(spec: ColumnSpec) -> Tuple[str, ...]:
    return (spec,) if isinstance(spec, str) else tuple(spec)


def make_unique_indexes(
        model: type,
        *,
        # Case-sensitive uniqueness specs (exact match)
        unique_cs: Iterable[ColumnSpec] = (),
        # Case-insensitive uniqueness specs: lower() applied to string columns
        unique_ci: Iterable[ColumnSpec] = (),
        # Optional tenant scoping (e.g. "tenant_id"). If provided:
        #   - when tenant is NULL -> global uniqueness
        #   - when tenant is NOT NULL -> uniqueness within tenant
        tenant_field: Optional[str] = None,
        # Prefix for index names
        name_prefix: str = "uq",
) -> List[Index]:
    """
    Returns a list of SQLAlchemy Index objects enforcing uniqueness.

    Notes:
    - For case-insensitive specs, we use functional unique indexes with lower(col).
    - If tenant_field is given and the tenant column is nullable, we generate two partial
      unique indexes: one for tenant IS NULL (global), one for tenant IS NOT NULL (scoped).
    - Attach these indexes after your model class definition, before migrations/DDL run:
        Indexes = make_unique_indexes(User, unique_ci=["email"], tenant_field="tenant_id")
        for ix in Indexes:
            ix.create(model.metadata.bind)  # OR just rely on Alembic autogenerate / metadata.create_all
      Most apps just *define* them at module import time:
        for ix in Indexes:  # they auto-register with the Table; no manual create() needed
            pass
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

    # Helper: name like uq_<table>_<tenant?>_<ci/cs>_<joined-columns>
    def _name(ci: bool, spec: Tuple[str, ...], null_bucket: Optional[str] = None):
        parts = [name_prefix, model.__tablename__]
        if tenant_field:
            parts.append(tenant_field)
        if null_bucket:
            parts.append(null_bucket)
        parts.append("ci" if ci else "cs")
        parts.extend(spec)
        return "_".join(parts)

    # Build indexes for both CS and CI specs
    for ci, spec_list in ((False, unique_cs), (True, unique_ci)):
        for spec in spec_list:
            spec_t = _as_tuple(spec)
            cols = _to_sa_cols(spec_t, ci=ci)

            if tenant_col is None:
                # simple global unique (with or without lower())
                idxs.append(Index(_name(ci, spec_t), *cols, unique=True))
            else:
                # two partial unique indexes to treat NULL tenant as its own bucket
                # 1) global bucket (tenant IS NULL)
                idxs.append(
                    Index(
                        _name(ci, spec_t, "null"),
                        *cols,
                        unique=True,
                        postgresql_where=tenant_col.is_(None),
                    )
                )
                # 2) per-tenant bucket (tenant IS NOT NULL)
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