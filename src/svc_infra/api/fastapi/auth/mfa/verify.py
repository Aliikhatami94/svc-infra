from typing import Literal

import pyotp
from pydantic import BaseModel

from svc_infra.api.fastapi.auth.mfa.pre_auth import get_mfa_pre_jwt_writer
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

from .models import EMAIL_OTP_STORE
from .utils import _hash, _now_utc_ts


class MFAProof(BaseModel):
    code: str | None = None
    pre_token: str | None = None


class MFAResult(BaseModel):
    ok: bool
    method: Literal["totp", "recovery", "email", "none"] = "none"
    attempts_left: int | None = None


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
