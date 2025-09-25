from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend

from svc_infra.api.fastapi import public_router
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

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


def mfa_login_router(
    *,
    fapi: FastAPIUsers,
    auth_backend: AuthenticationBackend,
    user_model: type,
    get_mfa_pre_writer,
    public_auth_prefix: str = "/auth",
) -> APIRouter:
    router = public_router(prefix=public_auth_prefix, tags=["auth"])

    @router.post("/login", name="auth:jwt.login")
    async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        scope: str = Form(""),
        client_id: str | None = Form(None),
        client_secret: str | None = Form(None),
        session: SqlSessionDep = Depends(),  # if your DI requires
    ):
        # 1) authenticate via backend's strategy (password)
        strategy = auth_backend.get_strategy()
        user = await fapi.get_user_manager().user_db.get_by_email(username)  # quick way
        if not user:
            raise HTTPException(400, "LOGIN_BAD_CREDENTIALS")
        # verify password
        from fastapi_users.password import PasswordHelper

        if not getattr(user, "is_active", True) or not PasswordHelper().verify(
            password, getattr(user, "hashed_password", None) or getattr(user, "password_hash", None)
        ):
            raise HTTPException(400, "LOGIN_BAD_CREDENTIALS")
        if getattr(user, "is_verified") is False:
            raise HTTPException(400, "LOGIN_USER_NOT_VERIFIED")

        # 2) MFA check
        if getattr(user, "mfa_enabled", False):
            pre = await get_mfa_pre_writer().write(user)
            # Tell client to call /auth/mfa/verify with code + pre_token
            return JSONResponse(
                status_code=401,
                content={"detail": "MFA_REQUIRED", "pre_token": pre},
            )

        # 3) otherwise mint normal token (cookie or json)
        token = await strategy.write_token(user)
        st = get_auth_settings()
        resp = JSONResponse({"access_token": token, "token_type": "bearer"})
        resp.set_cookie(
            key=st.auth_cookie_name,
            value=token,
            max_age=st.session_cookie_max_age_seconds,
            httponly=True,
            secure=bool(st.session_cookie_secure),
            samesite=str(st.session_cookie_samesite).lower(),
            domain=(st.session_cookie_domain or None),
            path="/",
        )
        return resp

    return router
