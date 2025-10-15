from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from svc_infra.api.fastapi.auth.security import Identity
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.security.models import AuthSession
from svc_infra.security.permissions import RequirePermission


def build_session_router() -> APIRouter:
    router = APIRouter(prefix="/sessions", tags=["sessions"])

    @router.get(
        "/me", response_model=list[dict], dependencies=[RequirePermission("security.session.list")]
    )
    async def list_my_sessions(identity: Identity, session: SqlSessionDep) -> List[dict]:
        stmt = select(AuthSession).where(AuthSession.user_id == identity.user.id)
        rows = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": str(r.id),
                "user_agent": r.user_agent,
                "ip_hash": r.ip_hash,
                "revoked": bool(r.revoked_at),
                "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    @router.post(
        "/{session_id}/revoke",
        status_code=204,
        dependencies=[RequirePermission("security.session.revoke")],
    )
    async def revoke_session(session_id: str, identity: Identity, db: SqlSessionDep):
        # Load session and ensure it belongs to the user (non-admin users cannot revoke others)
        s = await db.get(AuthSession, session_id)
        if not s:
            raise HTTPException(404, "session_not_found")
        # Basic ownership check; could extend for admin bypass later
        if s.user_id != identity.user.id:
            raise HTTPException(403, "forbidden")
        if s.revoked_at:
            return  # already revoked
        s.revoked_at = datetime.now(timezone.utc)
        s.revoke_reason = "user_revoked"
        # Revoke all refresh tokens for this session
        for rt in s.refresh_tokens:
            if not rt.revoked_at:
                rt.revoked_at = s.revoked_at
                rt.revoke_reason = "session_revoked"
        await db.flush()

    return router


__all__ = ["build_session_router"]
