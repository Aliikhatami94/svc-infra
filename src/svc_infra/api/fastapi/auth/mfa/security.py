from typing import Optional

from fastapi import Body, Depends, HTTPException, Query

from svc_infra.api.fastapi.auth.security import RequireUser
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

from .models import MFAProof
from .verify import verify_mfa_for_user


def RequireMFAIfEnabled(body_field: str = "mfa"):
    async def _dep(
        p=Depends(RequireUser()),
        sess: SqlSessionDep = Depends(),
        mfa: Optional[MFAProof] = Body(None, embed=True, alias=body_field),
        mfa_code: Optional[str] = Query(None, alias="mfa_code"),
        mfa_pre_token: Optional[str] = Query(None, alias="mfa_pre_token"),
    ):
        proof = mfa or (
            MFAProof(code=mfa_code, pre_token=mfa_pre_token)
            if (mfa_code or mfa_pre_token)
            else None
        )

        # Only force MFA if it's actually enabled for this user
        enabled = bool(getattr(p.user, "mfa_enabled", False))
        if not enabled:
            return p  # no MFA required

        res = await verify_mfa_for_user(
            user=p.user,
            session=sess,
            proof=proof,
            require_enabled=True,
        )
        if not res.ok:
            # bubble a clear client error; your exception middleware can keep it 400
            raise HTTPException(400, "Invalid code")

        return p

    return Depends(_dep)
