from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone
from typing import Literal

import pyotp
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi_users import FastAPIUsers
from pydantic import BaseModel
from sqlalchemy import select
from starlette.responses import JSONResponse

from svc_infra.api.fastapi.auth.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.auth.sender import get_sender
from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual.public import public_router

from .. import DualAPIRouter
from ..dual import user_router
from ._cookies import compute_cookie_params

# --- Email OTP store (replace with Redis in prod) ---
EMAIL_OTP_STORE: dict[str, dict] = {}  # key = uid (or jti), value={hash,exp,attempts,next_send}


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


class SendEmailCodeIn(BaseModel):
    pre_token: str


class SendEmailCodeOut(BaseModel):
    sent: bool = True
    cooldown_seconds: int = 60


class MFAStatusOut(BaseModel):
    enabled: bool
    methods: list[str]
    confirmed_at: datetime | None = None
    email_mask: str | None = None
    email_otp: dict | None = None


class MFAProof(BaseModel):
    code: str | None = None
    pre_token: str | None = None


class MFAResult(BaseModel):
    ok: bool
    method: Literal["totp", "recovery", "email", "none"] = "none"
    attempts_left: int | None = None


# ---- Utils ----
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


def _gen_numeric_code(n: int = 6) -> str:
    import random

    return "".join(str(random.randrange(10)) for _ in range(n))


def _now_utc_ts() -> int:
    from datetime import datetime, timezone

    return int(datetime.now(timezone.utc).timestamp())


async def verify_mfa_for_user(
    *,
    user,
    session: SqlSessionDep,
    proof: MFAProof | None,
    require_enabled: bool = True,
) -> MFAResult:
    """
    Verifies user MFA with one of:
      - TOTP (if mfa_secret set)
      - Recovery code (burns on success)
      - Email OTP (bound to pre_token; burns on success, decrements attempts on fail)

    Returns MFAResult(ok=..., method=..., attempts_left=...).
    If require_enabled=True and user has MFA enabled but no valid proof, returns ok=False.
    """
    # Quick short-circuit if user has no MFA
    enabled = bool(getattr(user, "mfa_enabled", False))
    if not enabled:
        return MFAResult(ok=not require_enabled, method="none", attempts_left=None)

    if not proof or not proof.code:
        return MFAResult(ok=False, method="none", attempts_left=None)

    # A) TOTP
    secret = getattr(user, "mfa_secret", None)
    if secret:
        totp = pyotp.TOTP(secret)
        if totp.verify(proof.code, valid_window=1):
            return MFAResult(ok=True, method="totp", attempts_left=None)

    # B) Recovery code
    dig = _hash(proof.code)
    recov = getattr(user, "mfa_recovery", None) or []
    if dig in recov:
        recov.remove(dig)  # burn one
        await session.flush()  # persist mutation for MutableList
        return MFAResult(ok=True, method="recovery", attempts_left=None)

    # C) Email OTP (requires pre_token → uid)
    if proof.pre_token:
        try:
            pre = await get_mfa_pre_jwt_writer().read(proof.pre_token)
            uid = str(pre.get("sub") or "")
        except Exception:
            uid = ""

        if uid and uid == str(user.id):
            rec = EMAIL_OTP_STORE.get(uid)
            now = _now_utc_ts()
            if rec:
                attempts_left = rec.get("attempts_left")
                if now <= rec["exp"] and attempts_left and attempts_left > 0 and rec["hash"] == dig:
                    EMAIL_OTP_STORE.pop(uid, None)  # burn on success
                    return MFAResult(ok=True, method="email", attempts_left=None)
                # decrement on failure
                rec["attempts_left"] = max(0, (attempts_left or 0) - 1)
                return MFAResult(ok=False, method="email", attempts_left=rec["attempts_left"])

    return MFAResult(ok=False, method="none", attempts_left=None)


# ---- Router factory ----
def mfa_router(
    *,
    user_model: type,
    get_strategy,  # from get_fastapi_users()
    fapi: FastAPIUsers,
    auth_prefix: str = "/auth",
) -> APIRouter:
    u = user_router(prefix=f"{auth_prefix}/mfa", tags=["auth:mfa"])
    p = public_router(prefix=f"{auth_prefix}/mfa", tags=["auth:mfa"])

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
        "/start",
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
        "/confirm",
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
        "/disable",
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

    @p.post("/verify")
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
        "/send_code",
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
        "/status",
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
        "/recovery/regenerate",
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
