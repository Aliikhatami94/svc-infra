from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend
from fastapi_users.password import PasswordHelper

from svc_infra.api.fastapi.auth._cookies import compute_cookie_params
from svc_infra.api.fastapi.auth.policy import AuthPolicy, DefaultAuthPolicy
from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.dual.public import public_router

_pwd = PasswordHelper()
_DUMMY_BCRYPT = _pwd.hash("dummy-password")


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


def auth_session_router(
    *,
    fapi: FastAPIUsers,
    auth_backend: AuthenticationBackend,
    user_model: type,
    get_mfa_pre_writer,
    public_auth_prefix: str = "/auth",
    auth_policy: AuthPolicy | None = None,
) -> APIRouter:
    router = public_router(prefix=public_auth_prefix, tags=["auth"])
    policy = auth_policy or DefaultAuthPolicy(get_auth_settings())

    @router.post("/login", name="auth:jwt.login")
    async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        scope: str = Form(""),
        client_id: str | None = Form(None),
        client_secret: str | None = Form(None),
        user_manager=Depends(fapi.get_user_manager),
    ):
        # 1) lookup user (normalize email)
        strategy = auth_backend.get_strategy()

        email = username.strip().lower()
        user = await user_manager.user_db.get_by_email(email)
        if not user:
            _, _ = _pwd.verify_and_update(password, _DUMMY_BCRYPT)
            raise HTTPException(400, "LOGIN_BAD_CREDENTIALS")

        # 2) verify status + password
        if not getattr(user, "is_active", True):
            raise HTTPException(401, "account_disabled")

        hashed = getattr(user, "hashed_password", None) or getattr(user, "password_hash", None)
        if not hashed:
            # No password set (likely OAuth-only account)
            raise HTTPException(400, "LOGIN_BAD_CREDENTIALS")

        ok, new_hash = _pwd.verify_and_update(password, hashed)
        if not ok:
            raise HTTPException(400, "LOGIN_BAD_CREDENTIALS")

        # If the hash needs upgrading, persist it (optional but recommended)
        if new_hash:
            if hasattr(user, "hashed_password"):
                user.hashed_password = new_hash
            elif hasattr(user, "password_hash"):
                user.password_hash = new_hash
            try:
                await user_manager.user_db.update(user)
            except Exception:
                # don't block login if updating hash fails; log if you have logging here
                pass

        if getattr(user, "is_verified") is False:
            raise HTTPException(400, "LOGIN_USER_NOT_VERIFIED")

        # 3) MFA policy check (user flag, tenant/global, etc.)
        if await policy.should_require_mfa(user):
            pre = await get_mfa_pre_writer().write(user)
            await policy.on_mfa_challenge(user)
            return JSONResponse(
                status_code=401,
                content={"detail": "MFA_REQUIRED", "pre_token": pre},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 4) record last_login for password logins that do NOT require MFA
        try:
            user.last_login = datetime.now(timezone.utc)
            await user_manager.user_db.update(user, {"last_login": user.last_login})
        except Exception:
            # don’t block login if this write fails
            pass

        # 5) mint token and set cookie
        token = await strategy.write_token(user)
        st = get_auth_settings()
        resp = JSONResponse({"access_token": token, "token_type": "bearer"})
        cp = compute_cookie_params(request, name=st.auth_cookie_name)
        resp.set_cookie(**cp, value=token)
        return resp

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, name="auth:logout")
    async def logout(request: Request):
        st = get_auth_settings()
        resp = JSONResponse({"ok": True})

        # Clear the auth cookie
        cp_auth = compute_cookie_params(request, name=st.auth_cookie_name)
        resp.delete_cookie(
            key=cp_auth["key"],
            path=cp_auth["path"],
            domain=cp_auth["domain"],
            samesite=cp_auth["samesite"],
            secure=cp_auth["secure"],
            httponly=cp_auth["httponly"],
        )

        # Clear the session middleware cookie
        cp_sess = compute_cookie_params(request, name=st.session_cookie_name)
        resp.delete_cookie(
            key=cp_sess["key"],
            path=cp_sess["path"],
            domain=cp_sess["domain"],
            samesite=cp_sess["samesite"],
            secure=cp_sess["secure"],
            httponly=cp_sess["httponly"],
        )

        # Optional but helpful in dev: nuke site cookies
        resp.headers["Clear-Site-Data"] = '"cookies"'

        return resp

    return router
