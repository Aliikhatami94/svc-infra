from __future__ import annotations

import pyotp
from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

from svc_infra.api.fastapi.auth.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.auth.routing import user_router
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

from .mfa import EMAIL_OTP_STORE, _hash, _now_utc_ts


class RequireMFAIn(BaseModel):
    code: str | None = None
    pre_token: str | None = None


class DisableAccountIn(RequireMFAIn):
    reason: str | None = None


class DeleteAccountIn(RequireMFAIn):
    hard: bool = False


def account_router(*, user_model: type, auth_prefix: str = "/auth") -> APIRouter:
    router = user_router(prefix=f"{auth_prefix}/account", tags=["auth:account"])

    async def _verify_code_for_user(user, code: str | None, pre_token: str | None) -> bool:
        if not code:
            return False
        if getattr(user, "mfa_secret", None) and pyotp.TOTP(user.mfa_secret).verify(
            code, valid_window=1
        ):
            return True
        dig = _hash(code)
        recov = getattr(user, "mfa_recovery", None) or []
        if dig in recov:
            recov.remove(dig)
            return True
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

    @router.post("/disable")
    async def disable_account(
        request: Request, session: SqlSessionDep, payload: DisableAccountIn | None = Body(None)
    ):
        p = request.state.principal
        user = p.user
        if getattr(user, "mfa_enabled", False):
            if not payload or not await _verify_code_for_user(
                user, payload.code, payload.pre_token
            ):
                raise HTTPException(400, "Invalid code")
            await session.flush()
        reason = (payload.reason if payload else None) or "user_disabled_self"
        user.is_active = False
        user.disabled_reason = reason
        await session.commit()
        return JSONResponse({"ok": True})

    @router.post("/delete")
    async def delete_account(
        request: Request, session: SqlSessionDep, payload: DeleteAccountIn | None = Body(None)
    ):
        p = request.state.principal
        user = p.user
        if getattr(user, "mfa_enabled", False):
            if not payload or not await _verify_code_for_user(
                user, payload.code, payload.pre_token
            ):
                raise HTTPException(400, "Invalid code")
            await session.flush()
        if payload and payload.hard:
            await session.delete(user)
            await session.commit()
            return JSONResponse({"ok": True, "deleted": "hard"})
        user.is_active = False
        user.disabled_reason = "user_soft_deleted"
        await session.commit()
        return JSONResponse({"ok": True, "deleted": "soft"})

    return router
