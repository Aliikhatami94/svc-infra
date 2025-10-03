from __future__ import annotations

from fastapi import APIRouter, Body, Query

from svc_infra.api.fastapi.auth.mfa.models import DisableAccountIn
from svc_infra.api.fastapi.auth.security import Identity
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual.protected import user_router
from svc_infra.api.fastapi.paths.user import DELETE_ACCOUNT_PATH, DISABLE_ACCOUNT_PATH


# ---------- Router ----------
def account_router(*, user_model: type) -> APIRouter:
    r = user_router()

    @r.patch(
        DISABLE_ACCOUNT_PATH,
        response_model=dict,
        description="Get account status (active/disabled)",
    )
    async def disable_account(
        sess: SqlSessionDep,
        p: Identity,
        payload: DisableAccountIn = Body(..., description="reason + mfa (if enabled)"),
    ):
        user = p.user
        user.is_active = False
        user.disabled_reason = payload.reason or "user_disabled_self"
        await sess.commit()
        return {"ok": True, "status": "disabled"}

    @r.delete(
        DELETE_ACCOUNT_PATH,
        status_code=204,
        description="Delete account (soft by default, hard if specified)",
    )
    async def delete_account(
        sess: SqlSessionDep,
        p: Identity,
        hard: bool = Query(False, description="Hard delete if true"),
    ):
        user = p.user
        if hard:
            await sess.delete(user)
            await sess.commit()
            return
        user.is_active = False
        user.disabled_reason = "user_soft_deleted"
        await sess.commit()
        return

    return r
