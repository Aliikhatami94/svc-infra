from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from pymongo import IndexModel

from svc_infra.db.utils import KeySpec
from svc_infra.db.utils import as_tuple as _as_tuple


def make_mongo_unique_indexes(
    *,
    collection_name: str,
    unique_cs: Iterable[KeySpec] = (),
    unique_ci: Iterable[KeySpec] = (),
    tenant_field: Optional[str] = None,
    name_prefix: str = "uq",
    ci_locale: str = "en",
) -> List[IndexModel]:
    from pymongo import ASCENDING, IndexModel
    from pymongo.collation import Collation

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

    idxs: List[IndexModel] = []

    # --- case-sensitive ---
    for spec in unique_cs:
        fields = _as_tuple(spec)
        if not tenant_field:
            idxs.append(IndexModel(_keys(fields), name=_name(False, fields), unique=True))
        else:
            # NULL bucket: enforce `tenant_id: null` (no $exists)
            idxs.append(
                IndexModel(
                    _keys(fields),
                    name=_name(False, fields, "null"),
                    unique=True,
                    partialFilterExpression={tenant_field: None},
                )
            )
            # NOT NULL bucket: include tenant first in the key
            idxs.append(
                IndexModel(
                    [(tenant_field, ASCENDING)] + _keys(fields),
                    name=_name(False, fields, "notnull"),
                    unique=True,
                    partialFilterExpression={tenant_field: {"$ne": None}},
                )
            )

    # --- case-insensitive (via collation) ---
    ci_collation = Collation(locale=ci_locale, strength=2)

    for spec in unique_ci:
        fields = _as_tuple(spec)
        if not tenant_field:
            idxs.append(
                IndexModel(
                    _keys(fields), name=_name(True, fields), unique=True, collation=ci_collation
                )
            )
        else:
            idxs.append(
                IndexModel(
                    _keys(fields),
                    name=_name(True, fields, "null"),
                    unique=True,
                    collation=ci_collation,
                    partialFilterExpression={tenant_field: None},
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
