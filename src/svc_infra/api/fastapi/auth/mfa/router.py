from __future__ import annotations

from datetime import datetime, timezone

import pyotp
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi_users import FastAPIUsers
from sqlalchemy import select
from starlette.responses import JSONResponse

from svc_infra.api.fastapi.auth._cookies import compute_cookie_params
from svc_infra.api.fastapi.auth.mfa.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.auth.sender import get_sender
from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual.protected import user_router
from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.api.fastapi.dual.router import DualAPIRouter

from ...paths.auth import (
    MFA_CONFIRM_PATH,
    MFA_DISABLE_PATH,
    MFA_REGENERATE_RECOVERY_PATH,
    MFA_SEND_CODE_PATH,
    MFA_START_PATH,
    MFA_STATUS_PATH,
    MFA_VERIFY_PATH,
)
from .models import (
    EMAIL_OTP_STORE,
    ConfirmSetupIn,
    DisableMFAIn,
    MFAStatusOut,
    RecoveryCodesOut,
    SendEmailCodeIn,
    SendEmailCodeOut,
    StartSetupOut,
    VerifyMFAIn,
)
from .utils import (
    _gen_numeric_code,
    _gen_recovery_codes,
    _hash,
    _now_utc_ts,
    _qr_svg_from_uri,
    _random_base32,
)


# ---- Router factory ----
def mfa_router(
    *,
    user_model: type,
    get_strategy,  # from get_fastapi_users()
    fapi: FastAPIUsers,
) -> APIRouter:
    u = user_router()
    p = public_router()

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
            user = await strategy.read_token(token, user_manager)  # fastapi-users user
            if not user:
                raise HTTPException(401, "Invalid token")
        except Exception:
            raise HTTPException(401, "Invalid token")

        # IMPORTANT: rehydrate into *your* session
        db_user = await session.get(user_model, user.id)
        if not db_user:
            raise HTTPException(401, "Invalid token")

        return db_user, session

    @u.post(
        MFA_START_PATH,
        response_model=StartSetupOut,
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

        # Update and COMMIT
        user.mfa_secret = secret
        user.mfa_enabled = False
        user.mfa_confirmed_at = None
        await session.commit()

        # (Optional) verify it actually persisted:
        # fresh_secret = (await session.execute(
        #     select(user_model.mfa_secret).where(user_model.id == user.id)
        # )).scalar_one()
        # assert fresh_secret == secret

        return StartSetupOut(otpauth_url=uri, secret=secret, qr_svg=_qr_svg_from_uri(uri))

    @u.post(
        MFA_CONFIRM_PATH,
        response_model=RecoveryCodesOut,
    )
    async def confirm_setup(
        payload: ConfirmSetupIn = Body(...), user_sess=Depends(_get_user_and_session)
    ):
        user, session = user_sess

        # RELOAD from DB to avoid stale state
        user = (
            await session.execute(select(user_model).where(user_model.id == user.id))
        ).scalar_one()

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
        await session.commit()

        return RecoveryCodesOut(codes=codes)

    @u.post(
        MFA_DISABLE_PATH,
        status_code=status.HTTP_204_NO_CONTENT,
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
        await session.commit()
        return JSONResponse(status_code=204, content={})

    @p.post(MFA_VERIFY_PATH)
    async def verify_mfa(
        request: Request,
        session: SqlSessionDep,
        payload: VerifyMFAIn = Body(...),
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
        if not user:
            raise HTTPException(401, "Invalid pre-auth token")

        # NEW: block disabled accounts here with a clear error
        if not getattr(user, "is_active", True):
            raise HTTPException(401, "account_disabled")

        if (not getattr(user, "mfa_enabled", False)) or (not getattr(user, "mfa_secret", None)):
            raise HTTPException(401, "MFA not enabled")

        # 3) verify TOTP or fallback
        ok = False

        # A) TOTP
        totp = pyotp.TOTP(user.mfa_secret)
        if totp.verify(payload.code, valid_window=1):
            ok = True
        else:
            # B) Recovery code
            dig = _hash(payload.code)
            if getattr(user, "mfa_recovery", None) and dig in user.mfa_recovery:
                user.mfa_recovery.remove(dig)
                await session.commit()  # persist burn
                ok = True
            else:
                # C) Email OTP (bound to uid via pre_token above)
                rec = EMAIL_OTP_STORE.get(str(uid))
                now = _now_utc_ts()
                if rec:
                    if (
                        now <= rec["exp"]
                        and rec["attempts_left"] > 0
                        and _hash(payload.code) == rec["hash"]
                    ):
                        ok = True
                        EMAIL_OTP_STORE.pop(str(uid), None)  # burn on success
                    else:
                        rec["attempts_left"] = max(0, rec["attempts_left"] - 1)

        if not ok:
            raise HTTPException(400, "Invalid code")

        # NEW: set last_login on successful MFA
        user.last_login = datetime.now(timezone.utc)
        await session.commit()

        # 4) mint normal JWT and set cookie
        token = await strategy.write_token(user)
        resp = JSONResponse({"access_token": token, "token_type": "bearer"})
        cp = compute_cookie_params(request, name=st.auth_cookie_name)  # <-- pass Request here
        resp.set_cookie(**cp, value=token)
        return resp

    @p.post(
        MFA_SEND_CODE_PATH,
        response_model=SendEmailCodeOut,
        description="Sends a 6-digit email OTP tied to the `pre_token`. Returns a resend cooldown.",
    )
    async def send_email_code(
        session: SqlSessionDep,
        payload: SendEmailCodeIn = Body(...),
    ):
        # 1) Validate pre_token and extract uid
        try:
            pre = await get_mfa_pre_jwt_writer().read(payload.pre_token)
            uid = pre.get("sub")
            if not uid:
                raise HTTPException(401, "Invalid pre-auth token")
        except Exception:
            raise HTTPException(401, "Invalid pre-auth token")

        # 1b) Load user to get their email
        user = await session.get(user_model, uid)
        if not user or not getattr(user, "email", None):
            # (optionally also check user.mfa_enabled here)
            raise HTTPException(401, "Invalid pre-auth token")

        st = get_auth_settings()
        now = _now_utc_ts()
        ttl = getattr(st, "email_otp_ttl_seconds", 5 * 60)
        cooldown = getattr(st, "email_otp_cooldown_seconds", 60)
        max_attempts = getattr(st, "email_otp_attempts", 5)

        # 2) Throttle resends
        rec = EMAIL_OTP_STORE.get(str(uid))
        if rec and rec.get("next_send") and now < rec["next_send"]:
            return SendEmailCodeOut(sent=True, cooldown_seconds=rec["next_send"] - now)

        # 3) Generate + store (hashed) OTP
        code = _gen_numeric_code(6)
        EMAIL_OTP_STORE[str(uid)] = {
            "hash": _hash(code),
            "exp": now + ttl,
            "attempts_left": max_attempts,
            "next_send": now + cooldown,
        }

        # 4) Send email
        sender = get_sender()
        sender.send(
            to=user.email,
            subject="Your sign-in code",
            html_body=f"""
                <p>Your code is: <b>{code}</b></p>
                <p>It expires in {ttl // 60} minutes.</p>
                <p>If you didn’t request this, you can ignore this email.</p>
            """,
        )

        return SendEmailCodeOut(sent=True, cooldown_seconds=cooldown)

    @u.get(
        MFA_STATUS_PATH,
        response_model=MFAStatusOut,
    )
    async def mfa_status(user_sess=Depends(_get_user_and_session)):
        user, _ = user_sess
        enabled = bool(getattr(user, "mfa_enabled", False))
        confirmed_at = getattr(user, "mfa_confirmed_at", None)

        methods = []
        if enabled and getattr(user, "mfa_secret", None):
            methods.append("totp")
            methods.append("recovery")
        # Email OTP is always offered in your flow at verify-time
        methods.append("email")

        def _mask(email: str) -> str:
            if not email or "@" not in email:
                return None
            name, domain = email.split("@", 1)
            if len(name) <= 1:
                masked = "*"
            elif len(name) == 2:
                masked = name[0] + "*"
            else:
                masked = name[0] + "*" * (len(name) - 2) + name[-1]
            return f"{masked}@{domain}"

        email = getattr(user, "email", None)
        st = get_auth_settings()
        return MFAStatusOut(
            enabled=enabled,
            methods=methods,
            confirmed_at=confirmed_at,
            email_mask=_mask(email) if email else None,
            email_otp={"cooldown_seconds": st.email_otp_cooldown_seconds},
        )

    @u.post(
        MFA_REGENERATE_RECOVERY_PATH,
        response_model=RecoveryCodesOut,
    )
    async def regenerate_recovery_codes(user_sess=Depends(_get_user_and_session)):
        user, session = user_sess
        if not getattr(user, "mfa_enabled", False):
            raise HTTPException(400, "MFA not enabled")

        st = get_auth_settings()
        codes = _gen_recovery_codes(st.mfa_recovery_codes, st.mfa_recovery_code_length)
        user.mfa_recovery = [_hash(c) for c in codes]
        await session.commit()
        return RecoveryCodesOut(codes=codes)

    router = DualAPIRouter()
    router.include_router(u)
    router.include_router(p)
    return router
