from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover
    AsyncSession = object  # type: ignore

from svc_infra.security.models import (
    AuthSession,
    RefreshToken,
    RefreshTokenRevocation,
    generate_refresh_token,
    hash_refresh_token,
    rotate_refresh_token,
)

DEFAULT_REFRESH_TTL_MINUTES = 60 * 24 * 7  # 7 days


async def issue_session_and_refresh(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: Optional[str] = None,
    user_agent: Optional[str] = None,
    ip_hash: Optional[str] = None,
    ttl_minutes: int = DEFAULT_REFRESH_TTL_MINUTES,
) -> tuple[str, RefreshToken]:
    """Persist a new AuthSession + initial RefreshToken and return raw refresh token.

    Returns: (raw_refresh_token, RefreshToken model instance)
    """
    session_row = AuthSession(
        user_id=user_id,
        tenant_id=tenant_id,
        user_agent=user_agent,
        ip_hash=ip_hash,
    )
    db.add(session_row)
    raw = generate_refresh_token()
    token_hash = hash_refresh_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    rt = RefreshToken(
        session=session_row,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(rt)
    await db.flush()
    return raw, rt


async def rotate_session_refresh(
    db: AsyncSession,
    *,
    current: RefreshToken,
    ttl_minutes: int = DEFAULT_REFRESH_TTL_MINUTES,
) -> tuple[str, RefreshToken]:
    """Rotate a session's refresh token: mark current rotated, create new, add revocation record.

    Returns: (new_raw_refresh_token, new_refresh_token_model)
    """
    new_raw, new_hash, expires_at = rotate_refresh_token(
        current.token_hash, ttl_minutes=ttl_minutes
    )
    current.rotated_at = datetime.now(timezone.utc)
    # create revocation entry for old hash
    db.add(
        RefreshTokenRevocation(
            token_hash=current.token_hash,
            revoked_at=current.rotated_at,
            reason="rotated",
        )
    )
    new_row = RefreshToken(
        session=current.session,
        token_hash=new_hash,
        expires_at=expires_at,
    )
    db.add(new_row)
    await db.flush()
    return new_raw, new_row


__all__ = ["issue_session_and_refresh", "rotate_session_refresh"]
