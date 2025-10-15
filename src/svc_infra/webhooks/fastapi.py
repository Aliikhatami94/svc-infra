from __future__ import annotations

from typing import Callable, Sequence

from fastapi import HTTPException, Request, status

from .signing import verify, verify_any


def require_signature(
    secrets_provider: Callable[[], str | Sequence[str]],
    *,
    header_name: str = "X-Signature",
):
    async def _dep(request: Request):
        sig = request.headers.get(header_name)
        if not sig:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="missing signature"
            )
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid JSON body")
        secrets = secrets_provider()
        ok = False
        if isinstance(secrets, str):
            ok = verify(secrets, body, sig)
        else:
            ok = verify_any(secrets, body, sig)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature"
            )
        return body

    return _dep
