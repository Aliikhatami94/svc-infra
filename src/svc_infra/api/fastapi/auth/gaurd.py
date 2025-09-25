from __future__ import annotations

from fastapi import HTTPException, Request, status

from .settings import get_auth_settings


async def login_client_guard(request: Request):
    """
    If AUTH_REQUIRE_CLIENT_SECRET_ON_PASSWORD_LOGIN is True,
    require client_id/client_secret on POST .../login requests.
    Applied at the router level; we only enforce for the /login subpath.
    """
    st = get_auth_settings()
    if not bool(getattr(st, "require_client_secret_on_password_login", False)):
        return

    # only enforce on the login endpoint (form-encoded)
    if request.method.upper() == "POST" and request.url.path.endswith("/login"):
        try:
            form = await request.form()
        except Exception:
            form = {}

        client_id = (form.get("client_id") or "").strip()
        client_secret = (form.get("client_secret") or "").strip()
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="client_credentials_required"
            )

        # validate against configured clients
        ok = False
        for pc in getattr(st, "password_clients", []) or []:
            if pc.client_id == client_id and pc.client_secret.get_secret_value() == client_secret:
                ok = True
                break

        if not ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_client_credentials"
            )
