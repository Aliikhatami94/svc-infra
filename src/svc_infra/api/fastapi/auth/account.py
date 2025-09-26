from __future__ import annotations

import pyotp
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Security
from pydantic import BaseModel
from starlette.responses import JSONResponse

from svc_infra.api.fastapi import public_router
from svc_infra.api.fastapi.auth.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.auth.settings import get_auth_settings
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

from .mfa import EMAIL_OTP_STORE, _hash, _now_utc_ts  # reuse helpers
from .security import cookie_auth_optional, oauth2_scheme_optional


class RequireMFAIn(BaseModel):
    code: str | None = None
    pre_token: str | None = None


class DisableAccountIn(RequireMFAIn):
    reason: str | None = None


class DeleteAccountIn(RequireMFAIn):
    hard: bool = False  # soft by default


def account_router(
    *,
    user_model: type,
    auth_prefix: str = "/auth",
) -> APIRouter:
    router = public_router(prefix=f"{auth_prefix}/account", tags=["auth:account"])

    async def _current_user(request: Request, session: SqlSessionDep):
        st = get_auth_settings()
        token = request.headers.get("authorization", "").removeprefix(
            "Bearer "
        ).strip() or request.cookies.get(st.auth_cookie_name)
        if not token:
            raise HTTPException(401, "Missing token")

        # Read token via your strategy (same as elsewhere)
        from svc_infra.api.fastapi.db.sql.users import get_fastapi_users

        fapi, auth_backend, *_ = get_fastapi_users(
            user_model, None, None, None, public_auth_prefix=auth_prefix
        )
        # IMPORTANT: get a real user_manager instance to pass into read_token
        user_manager_gen = fapi.get_user_manager
        async for user_manager in user_manager_gen():  # type: ignore
            strategy = auth_backend.get_strategy()
            try:
                user = await strategy.read_token(token, user_manager)
            finally:
                break  # we only need one instance

        if not user:
            raise HTTPException(401, "Invalid token")

        db_user = await session.get(user_model, user.id)
        if not db_user:
            raise HTTPException(401, "Invalid token")
        if not getattr(db_user, "is_active", True):
            raise HTTPException(401, "account_disabled")

        return db_user, session

    async def _verify_code_for_user(user, code: str | None, pre_token: str | None) -> bool:
        """Accept TOTP, recovery, or email OTP (requires pre_token for email)."""
        if not code:
            return False
        # TOTP
        if getattr(user, "mfa_secret", None):
            if pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
                return True
        # Recovery
        dig = _hash(code)
        recov = getattr(user, "mfa_recovery", None) or []
        if dig in recov:
            recov.remove(dig)
            return True
        # Email OTP
        if pre_token:
            try:
                pre = await get_mfa_pre_jwt_writer().read(pre_token)
                uid = str(pre.get("sub") or "")
            except Exception:
                uid = ""
            if uid and uid == str(user.id):
                rec = EMAIL_OTP_STORE.get(uid)
                now = _now_utc_ts()
                if (
                    rec
                    and now <= rec["exp"]
                    and rec["attempts_left"] > 0
                    and _hash(code) == rec["hash"]
                ):
                    EMAIL_OTP_STORE.pop(uid, None)
                    return True
                if rec:
                    rec["attempts_left"] = max(0, rec["attempts_left"] - 1)
        return False

    @router.post(
        "/disable", openapi_extra={"security": [{"OAuth2PasswordBearer": []}, {"cookieAuth": []}]}
    )
    async def disable_account(
        _b: str | None = Security(oauth2_scheme_optional),
        _c: str | None = Security(cookie_auth_optional),
        payload: DisableAccountIn | None = Body(None),
        dep=Depends(_current_user),
    ):
        user, session = dep

        if getattr(user, "mfa_enabled", False):
            if not payload or not await _verify_code_for_user(
                user, payload.code, payload.pre_token
            ):
                raise HTTPException(400, "Invalid code")
            await session.flush()  # burns recovery code if used

        reason = (payload.reason if payload else None) or "user_disabled_self"
        user.is_active = False
        user.disabled_reason = reason
        await session.commit()
        return JSONResponse({"ok": True})

    @router.post(
        "/delete", openapi_extra={"security": [{"OAuth2PasswordBearer": []}, {"cookieAuth": []}]}
    )
    async def delete_account(
        payload: DeleteAccountIn | None = Body(None), dep=Depends(_current_user)
    ):
        user, session = dep

        if getattr(user, "mfa_enabled", False):
            if not payload or not await _verify_code_for_user(
                user, payload.code, payload.pre_token
            ):
                raise HTTPException(400, "Invalid code")
            await session.flush()

        hard = bool(payload.hard) if payload else False
        if hard:
            await session.delete(user)
            await session.commit()
            return JSONResponse({"ok": True, "deleted": "hard"})
        else:
            user.is_active = False
            user.disabled_reason = "user_soft_deleted"
            await session.commit()
            return JSONResponse({"ok": True, "deleted": "soft"})

    return router
