from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
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
    # Optional inline SVG (no extra deps). You can swap to `qrcode` lib if you prefer PNGs.
    # Very tiny placeholder: render URI as text; frontends will usually build QR anyway.
    return f"<svg xmlns='http://www.w3.org/2000/svg' width='280' height='280'><rect width='100%' height='100%' fill='#fff'/><text x='10' y='20' font-size='10'>{uri}</text></svg>"


def _random_base32(nbytes: int = 20) -> str:
    return pyotp.random_base32(length=32)  # safe default


def _gen_recovery_codes(n: int, length: int) -> list[str]:
    # human-ish codes like XXXX-YYYY
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
    get_strategy,  # the function returned from your get_fastapi_users()
    auth_prefix: str = "/auth",
) -> APIRouter:
    router = public_router(prefix=f"{auth_prefix}/mfa", tags=["auth:mfa"])

    # Dependency to get current user if already logged in (for setup/disable)
    # Re-use your optional/require deps if you prefer; here we inline a minimal variant using your session dep.
    async def _get_user_and_session(request: Request, session: SqlSessionDep):
        # If you already have a @require_user dep, use that. Otherwise this demo expects
        # Authorization: Bearer <access token> or cookie as in your other routes.
        strategy = get_strategy()
        token = request.headers.get("authorization", "").replace(
            "Bearer ", ""
        ) or request.cookies.get(get_auth_settings().auth_cookie_name)
        if not token:
            raise HTTPException(401, "Missing token")
        try:
            payload = await strategy.read_token(token, token_type="access")
            sub = payload.get("sub")
        except Exception:
            raise HTTPException(401, "Invalid token")
        user = await session.get(user_model, sub)
        if not user:
            raise HTTPException(401, "Invalid token")
        return user, session

    @router.post("/start", response_model=StartSetupOut)
    async def start_setup(user_sess=Depends(_get_user_and_session)):
        user, session = user_sess
        if getattr(user, "mfa_enabled", False):
            raise HTTPException(400, "MFA already enabled")

        st = get_auth_settings()
        secret = _random_base32()
        issuer = st.mfa_issuer
        label = user.email or f"user-{user.id}"
        uri = pyotp.totp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)

        # stash secret temporarily until confirmed
        user.mfa_secret = secret
        user.mfa_enabled = False
        user.mfa_confirmed_at = None
        await session.flush()

        return StartSetupOut(otpauth_url=uri, secret=secret, qr_svg=_qr_svg_from_uri(uri))

    @router.post("/confirm", response_model=RecoveryCodesOut)
    async def confirm_setup(payload: ConfirmSetupIn, user_sess=Depends(_get_user_and_session)):
        user, session = user_sess
        if not user.mfa_secret:
            raise HTTPException(400, "No setup in progress")

        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(payload.code, valid_window=1):
            raise HTTPException(400, "Invalid code")

        st = get_auth_settings()
        codes = _gen_recovery_codes(st.mfa_recovery_codes, st.mfa_recovery_code_length)
        # store hashed codes
        user.mfa_recovery = [_hash(c) for c in codes]
        user.mfa_enabled = True
        user.mfa_confirmed_at = datetime.now(timezone.utc)
        await session.flush()

        return RecoveryCodesOut(codes=codes)

    @router.post("/disable")
    async def disable_mfa(payload: DisableMFAIn, user_sess=Depends(_get_user_and_session)):
        user, session = user_sess
        if not user.mfa_enabled:
            return JSONResponse(status_code=204, content={})

        # Require either a valid TOTP code or a recovery code
        ok = False
        if payload.code and user.mfa_secret:
            totp = pyotp.TOTP(user.mfa_secret)
            ok = totp.verify(payload.code, valid_window=1)
        if not ok and payload.recovery_code and user.mfa_recovery:
            dig = _hash(payload.recovery_code)
            if dig in user.mfa_recovery:
                # burn one code
                user.mfa_recovery.remove(dig)
                ok = True

        if not ok:
            raise HTTPException(400, "Invalid code")

        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_recovery = None
        user.mfa_confirmed_at = None
        await session.flush()
        return JSONResponse(status_code=204, content={})

    # --------- Challenge: exchange pre-auth token + TOTP for real session ---------
    @router.post("/verify")
    async def verify_mfa(payload: VerifyMFAIn, session: SqlSessionDep, request: Request):
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
        if not user or not user.mfa_enabled or not user.mfa_secret:
            raise HTTPException(401, "MFA not enabled")

        # 3) verify TOTP or recovery
        ok = False
        totp = pyotp.TOTP(user.mfa_secret)
        if totp.verify(payload.code, valid_window=1):
            ok = True
        else:
            # allow recovery code here too
            dig = _hash(payload.code)
            if user.mfa_recovery and dig in user.mfa_recovery:
                user.mfa_recovery.remove(dig)
                await session.flush()
                ok = True
        if not ok:
            raise HTTPException(400, "Invalid code")

        # 4) mint normal JWT and set cookie (same as your OAuth callback)
        token = await strategy.write_token(user)  # audience fastapi-users:auth
        resp = JSONResponse({"ok": True})
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
