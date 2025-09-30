from typing import Optional

from fastapi import Body, Depends, HTTPException, Query

from svc_infra.api.fastapi.auth.security import Identity
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

from .models import MFAProof
from .verify import verify_mfa_for_user


def RequireMFAIfEnabled(body_field: str = "mfa"):
    async def _dep(
        p: Identity,
        sess: SqlSessionDep,
        mfa: Optional[MFAProof] = Body(None, embed=True, alias=body_field),
        mfa_code: Optional[str] = Query(None, alias="mfa_code"),
        mfa_pre_token: Optional[str] = Query(None, alias="mfa_pre_token"),
    ):
        proof = mfa or (
            MFAProof(code=mfa_code, pre_token=mfa_pre_token) if mfa_code or mfa_pre_token else None
        )
        res = await verify_mfa_for_user(
            user=p.user,
            session=sess,
            proof=proof,
            require_enabled=False,  # <— key change
        )
        if not res.ok:
            # Only raise if MFA is actually enabled for this user
            if getattr(p.user, "mfa_enabled", False):
                raise HTTPException(400, "Invalid code")
        return p

    return Depends(_dep)
