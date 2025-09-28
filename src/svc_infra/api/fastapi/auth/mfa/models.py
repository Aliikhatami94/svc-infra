from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# --- Email OTP store (replace with Redis in prod) ---
EMAIL_OTP_STORE: dict[str, dict] = {}  # key = uid (or jti), value={hash,exp,attempts,next_send}


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


class DisableAccountIn(BaseModel):
    reason: Optional[str] = None
    mfa: Optional[MFAProof] = None


class DeleteAccountIn(BaseModel):
    mfa: Optional[MFAProof] = None
