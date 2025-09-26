from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone

import pyotp
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi_users import FastAPIUsers
from pydantic import BaseModel
from starlette.responses import JSONResponse

from svc_infra.api.fastapi import public_router
from svc_infra.api.fastapi.auth.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep


# ---- DTOs ----
class StartSetupOut(BaseModel):
    otpauth_url: str
    secret: str
    qr_svg: str | None = None  # optional: inline SVG


class ConfirmSetupIn(BaseModel):
    code: str


class VerifyMFAIn(BaseModel):
    code: str
    pre_token: str


class DisableMFAIn(BaseModel):
    code: str | None = None
    recovery_code: str | None = None


class RecoveryCodesOut(BaseModel):
    codes: list[str]


def _qr_svg_from_uri(uri: str) -> str:
    # Placeholder SVG; most frontends will render their own QR
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='280' height='280'>"
        "<rect width='100%' height='100%' fill='#fff'/>"
        f"<text x='10' y='20' font-size='10'>{uri}</text></svg>"
    )


def _random_base32() -> str:
    return pyotp.random_base32(length=32)


def _gen_recovery_codes(n: int, length: int) -> list[str]:
    out = []
    for _ in range(n):
        raw = base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")
        out.append(raw[:length])
    return out


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def mfa_router(
    *,
    user_model: type,
    get_strategy,  # from get_fastapi_users()
    fapi: FastAPIUsers,
    auth_prefix: str = "/auth",
) -> APIRouter:
    router = public_router(prefix=f"{auth_prefix}/mfa", tags=["auth:mfa"])

    # Resolve current user via cookie OR bearer, using fastapi-users v10 strategy.read_token(..., user_manager)
    async def _get_user_and_session(
        request: Request,
        session: SqlSessionDep,
        user_manager=Depends(fapi.get_user_manager),
    ):
        st = get_auth_settings()
        token = request.headers.get("authorization", "").removeprefix(
            "Bearer "
        ).strip() or request.cookies.get(st.auth_cookie_name)
        if not token:
            raise HTTPException(401, "Missing token")

        strategy = get_strategy()
        try:
            # v10 returns a User object or None
            user = await strategy.read_token(token, user_manager)
            if not user:
                raise HTTPException(401, "Invalid token")
        except Exception:
            raise HTTPException(401, "Invalid token")

        return user, session

    @router.post(
        "/start",
        response_model=StartSetupOut,
        openapi_extra={"security": [{"OAuth2PasswordBearer": []}]},
    )
    async def start_setup(user_sess=Depends(_get_user_and_session)):
        user, session = user_sess
        if getattr(user, "mfa_enabled", False):
            raise HTTPException(400, "MFA already enabled")

        st = get_auth_settings()
        secret = _random_base32()
        issuer = st.mfa_issuer
        label = getattr(user, "email", None) or f"user-{user.id}"
        uri = pyotp.totp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)

        # Stage secret until confirmed
        user.mfa_secret = secret
        user.mfa_enabled = False
        user.mfa_confirmed_at = None
        await session.flush()

        return StartSetupOut(otpauth_url=uri, secret=secret, qr_svg=_qr_svg_from_uri(uri))

    @router.post(
        "/confirm",
        response_model=RecoveryCodesOut,
        openapi_extra={"security": [{"OAuth2PasswordBearer": []}]},
    )
    async def confirm_setup(
        payload: ConfirmSetupIn = Body(...),
        user_sess=Depends(_get_user_and_session),
    ):
        user, session = user_sess
        if not getattr(user, "mfa_secret", None):
            raise HTTPException(400, "No setup in progress")

        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(payload.code, valid_window=1):
            raise HTTPException(400, "Invalid code")

        st = get_auth_settings()
        codes = _gen_recovery_codes(st.mfa_recovery_codes, st.mfa_recovery_code_length)

        user.mfa_recovery = [_hash(c) for c in codes]
        user.mfa_enabled = True
        user.mfa_confirmed_at = datetime.now(timezone.utc)
        await session.flush()

        return RecoveryCodesOut(codes=codes)

    @router.post(
        "/disable",
        openapi_extra={"security": [{"OAuth2PasswordBearer": []}]},
    )
    async def disable_mfa(
        payload: DisableMFAIn = Body(...),
        user_sess=Depends(_get_user_and_session),
    ):
        user, session = user_sess
        if not getattr(user, "mfa_enabled", False):
            return JSONResponse(status_code=204, content={})

        ok = False
        if payload.code and getattr(user, "mfa_secret", None):
            totp = pyotp.TOTP(user.mfa_secret)
            ok = totp.verify(payload.code, valid_window=1)

        if not ok and payload.recovery_code and getattr(user, "mfa_recovery", None):
            dig = _hash(payload.recovery_code)
            if dig in user.mfa_recovery:
                user.mfa_recovery.remove(dig)  # burn one
                ok = True

        if not ok:
            raise HTTPException(400, "Invalid code")

        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_recovery = None
        user.mfa_confirmed_at = None
        await session.flush()
        return JSONResponse(status_code=204, content={})

    @router.post(
        "/verify",
        openapi_extra={"security": [{"OAuth2PasswordBearer": []}]},
    )
    async def verify_mfa(
        payload: VerifyMFAIn = Body(...),
        session: SqlSessionDep = Depends(),
    ):
        st = get_auth_settings()
        strategy = get_strategy()

        # 1) read/verify pre-auth token (aud = mfa)
        try:
            pre = await get_mfa_pre_jwt_writer().read(payload.pre_token)
            uid = pre.get("sub")
            if not uid:
                raise HTTPException(401, "Invalid pre-auth token")
        except Exception:
            raise HTTPException(401, "Invalid pre-auth token")

        # 2) load user
        user = await session.get(user_model, uid)
        if (
            not user
            or not getattr(user, "mfa_enabled", False)
            or not getattr(user, "mfa_secret", None)
        ):
            raise HTTPException(401, "MFA not enabled")

        # 3) verify TOTP or recovery
        ok = False
        totp = pyotp.TOTP(user.mfa_secret)
        if totp.verify(payload.code, valid_window=1):
            ok = True
        else:
            dig = _hash(payload.code)
            if getattr(user, "mfa_recovery", None) and dig in user.mfa_recovery:
                user.mfa_recovery.remove(dig)
                await session.flush()
                ok = True
        if not ok:
            raise HTTPException(400, "Invalid code")

        # 4) mint normal JWT and set cookie
        token = await strategy.write_token(user)
        resp = JSONResponse({"ok": True})
        resp.set_cookie(
            key=st.auth_cookie_name,
            value=token,
            max_age=st.session_cookie_max_age_seconds,
            httponly=True,
            secure=bool(st.session_cookie_secure),
            samesite=str(st.session_cookie_samesite).lower(),
            domain=(getattr(st, "session_cookie_domain", None) or None),
            path="/",
        )
        return resp

    return router
