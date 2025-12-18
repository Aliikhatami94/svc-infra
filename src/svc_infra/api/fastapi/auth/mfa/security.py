from fastapi import Body, Depends, HTTPException, Query

from svc_infra.api.fastapi.auth.security import Identity
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

from .verify import MFAProof, verify_mfa_for_user


def RequireMFAIfEnabled(body_field: str = "mfa"):
    async def _dep(
        p: Identity,
        sess: SqlSessionDep,
        mfa: MFAProof | None = Body(None, embed=True, alias=body_field),
        mfa_code: str | None = Query(None, alias="mfa_code"),
        mfa_pre_token: str | None = Query(None, alias="mfa_pre_token"),
    ):
        proof = mfa or (
            MFAProof(code=mfa_code, pre_token=mfa_pre_token)
            if (mfa_code or mfa_pre_token)
            else None
        )
        if not getattr(p.user, "mfa_enabled", False):
            return p
        res = await verify_mfa_for_user(
            user=p.user, session=sess, proof=proof, require_enabled=True
        )
        if not res.ok:
            raise HTTPException(400, "Invalid code")
        return p

    return Depends(_dep)
