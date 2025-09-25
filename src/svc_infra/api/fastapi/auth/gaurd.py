from __future__ import annotations

import base64
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from starlette import status

from .settings import get_auth_settings


def _parse_basic(header: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not header or not header.lower().startswith("basic "):
        return None, None
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        cid, csec = decoded.split(":", 1)
        return cid, csec
    except Exception:
        return None, None


async def login_client_guard(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),  # includes client_id/client_secret fields
) -> None:
    # Only enforce on the password login route
    if request.method.upper() != "POST" or not request.url.path.endswith("/login"):
        return

    st = get_auth_settings()
    clients = getattr(st, "password_clients", []) or []
    require = bool(getattr(st, "require_client_secret_on_password_login", False))

    # Collect creds from either the form or Basic auth header
    cid = form.client_id
    csec = form.client_secret
    if not cid or not csec:
        b_cid, b_sec = _parse_basic(request.headers.get("authorization"))
        cid = cid or b_cid
        csec = csec or b_sec

    if not clients:
        # No clients configured: allow if not required; otherwise reject.
        if require:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
        return

    # If not “require” and user didn’t send client creds, allow
    if not require and not (cid and csec):
        return

    # Validate against configured list
    for c in clients:
        if c.client_id == cid and c.client_secret.get_secret_value() == (csec or ""):
            return

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
