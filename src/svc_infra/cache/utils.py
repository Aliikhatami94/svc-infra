import hashlib
import json
from typing import Any, Iterable


def stable_hash(*args: Any, **kwargs: Any) -> str:
    try:
        raw = json.dumps([args, kwargs], default=str, sort_keys=True, separators=(",", ":"))
    except Exception:
        raw = repr((args, kwargs))
    return hashlib.sha1(raw.encode()).hexdigest()


def join_key(parts: Iterable[str]) -> str:
    return ":".join(p.strip(":") for p in parts if p is not None and p != "")


def format_tuple_key(key_tuple: tuple[str, ...], **kwargs) -> str:
    # BUGFIX: previously referenced _join_key (undefined). Use join_key.
    return join_key(part.format(**kwargs) for part in key_tuple)
