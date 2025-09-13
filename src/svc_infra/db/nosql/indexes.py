from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.collation import Collation

# Devs can hand you either a ready IndexModel or a dict alias. We normalize to IndexModel.
# Dict alias shape:
# {
#   "keys": [("field", 1), ("other", -1)]  # or ["field", "-other"]
#   "unique": True/False,
#   "name": "idx_name",
#   "partialFilterExpression": {...},
#   "expireAfterSeconds": 3600,
#   "collation": {"locale":"en", "strength":2},
#   "sparse": True/False,
#   "background": True/False   # ignored by MongoDB 6+, harmless to pass
# }
Alias = Dict[str, Any]
KeySpec = Union[str, Tuple[str, int]]


def _normalize_keys(keys: Iterable[KeySpec]) -> List[Tuple[str, int]]:
    out: List[Tuple[str, int]] = []
    for k in keys:
        if isinstance(k, tuple):
            field, dir_val = k
            direction = ASCENDING if dir_val >= 0 else DESCENDING
            out.append((field, direction))
        else:
            # string form: "field" => ASC; "-field" => DESC
            name = k[1:] if k.startswith("-") else k
            direction = DESCENDING if k.startswith("-") else ASCENDING
            out.append((name, direction))
    return out


def _normalize_collation(c: Optional[Dict[str, Any]]) -> Optional[Collation]:
    if not c:
        return None
    # common short form e.g. {"locale":"en","strength":2}
    return Collation(**c)


def normalize_index(idx: Union[IndexModel, Alias]) -> IndexModel:
    if isinstance(idx, IndexModel):
        return idx
    keys = _normalize_keys(idx.get("keys", []))
    if not keys:
        raise ValueError("Index alias requires 'keys'.")
    kwargs: Dict[str, Any] = {}
    for k in (
        "name",
        "unique",
        "partialFilterExpression",
        "sparse",
        "expireAfterSeconds",
        "background",
    ):
        if k in idx:
            kwargs[k] = idx[k]
    collation = _normalize_collation(idx.get("collation"))
    if collation:
        kwargs["collation"] = collation
    return IndexModel(keys, **kwargs)


def normalize_indexes(indexes: Optional[Iterable[Union[IndexModel, Alias]]]) -> List[IndexModel]:
    if not indexes:
        return []
    return [normalize_index(i) for i in indexes]
