from __future__ import annotations

from typing import Annotated, Any, Callable, Optional

from fastapi import Header, HTTPException


async def require_if_match(
    version: Annotated[Optional[str], Header(alias="If-Match")] = None
) -> str:
    """Require If-Match header for optimistic locking on mutating operations.

    Returns the header value. Raises 428 if missing.
    """
    if not version:
        raise HTTPException(
            status_code=428, detail="Missing If-Match header for optimistic locking."
        )
    return version


def check_version_or_409(get_current_version: Callable[[], Any], provided: str) -> None:
    """Compare provided version with current version; raise 409 on mismatch.

    - get_current_version: callable returning the resource's current version (int/str)
    - provided: header value; attempts to coerce to int if current is int
    """
    current = get_current_version()
    if isinstance(current, int):
        try:
            p = int(provided)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid If-Match value; expected integer.")
    else:
        p = provided
    if p != current:
        raise HTTPException(status_code=409, detail="Version mismatch (optimistic locking).")
