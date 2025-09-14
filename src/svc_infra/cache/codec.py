from __future__ import annotations

import json
from typing import Any


def dumps(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), default=str).encode("utf-8")


def loads(b: bytes | None) -> Any:
    if b is None:
        return None
    return json.loads(b.decode("utf-8"))
