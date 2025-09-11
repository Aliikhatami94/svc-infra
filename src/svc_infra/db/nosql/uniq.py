from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple, Union

from pymongo import ASCENDING, IndexModel
from pymongo.collation import Collation

# ColumnSpec: a field name or a tuple/list of field names
FieldSpec = Union[str, Sequence[str]]


def _as_tuple(spec: FieldSpec) -> Tuple[str, ...]:
    return (spec,) if isinstance(spec, str) else tuple(spec)


def make_mongo_unique_indexes(
    *,
    collection_name: str,
    unique_cs: Iterable[FieldSpec] = (),
    unique_ci: Iterable[FieldSpec] = (),
    tenant_field: Optional[str] = None,
    name_prefix: str = "uq",
    # case-insensitive: use collation strength=2 (English default); override by passing locale
    ci_locale: str = "en",
) -> List[IndexModel]:
    """
    Build pymongo IndexModel objects for uniqueness:
      - unique_cs: case-sensitive unique indexes
      - unique_ci: case-insensitive unique (via index-level collation)
      - tenant_field: split uniqueness into two partial indexes:
            tenant is NULL (missing/None) — global bucket
            tenant is NOT NULL — scoped per-tenant (include tenant first)
    For multi-field specs, order is preserved. Default sort is ASCENDING.
    """
    idxs: List[IndexModel] = []

    def _name(ci: bool, spec: Tuple[str, ...], bucket: Optional[str] = None) -> str:
        parts = [name_prefix, collection_name]
        if tenant_field:
            parts.append(tenant_field)
        if bucket:
            parts.append(bucket)
        parts.append("ci" if ci else "cs")
        parts.extend(spec)
        return "_".join(parts)

    def _keys(spec: Tuple[str, ...]) -> List[tuple[str, int]]:
        return [(f, ASCENDING) for f in spec]

    # case-sensitive
    for spec in unique_cs:
        fields = _as_tuple(spec)
        if not tenant_field:
            idxs.append(IndexModel(_keys(fields), name=_name(False, fields), unique=True))
            continue

        # tenant NULL bucket (global clashes)
        idxs.append(
            IndexModel(
                _keys(fields),
                name=_name(False, fields, "null"),
                unique=True,
                partialFilterExpression={
                    "$or": [
                        {tenant_field: {"$exists": False}},
                        {tenant_field: None},
                    ]
                },
            )
        )
        # tenant NOT NULL bucket: include tenant first in key for per-tenant uniqueness
        idxs.append(
            IndexModel(
                [(tenant_field, ASCENDING)] + _keys(fields),
                name=_name(False, fields, "notnull"),
                unique=True,
                partialFilterExpression={tenant_field: {"$ne": None}},
            )
        )

    # case-insensitive (via collation)
    ci_collation = Collation(locale=ci_locale, strength=2)

    for spec in unique_ci:
        fields = _as_tuple(spec)
        if not tenant_field:
            idxs.append(
                IndexModel(
                    _keys(fields), name=_name(True, fields), unique=True, collation=ci_collation
                )
            )
            continue

        idxs.append(
            IndexModel(
                _keys(fields),
                name=_name(True, fields, "null"),
                unique=True,
                collation=ci_collation,
                partialFilterExpression={
                    "$or": [
                        {tenant_field: {"$exists": False}},
                        {tenant_field: None},
                    ]
                },
            )
        )
        idxs.append(
            IndexModel(
                [(tenant_field, ASCENDING)] + _keys(fields),
                name=_name(True, fields, "notnull"),
                unique=True,
                collation=ci_collation,
                partialFilterExpression={tenant_field: {"$ne": None}},
            )
        )

    return idxs
