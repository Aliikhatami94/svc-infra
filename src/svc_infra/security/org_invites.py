from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover
    AsyncSession = object  # type: ignore
    select = None  # type: ignore

from .models import OrganizationInvitation, OrganizationMembership


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _new_token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


async def issue_invitation(
    db: Any,
    *,
    org_id: uuid.UUID,
    email: str,
    role: str,
    created_by: Optional[uuid.UUID] = None,
    ttl_hours: int = 72,
) -> tuple[str, OrganizationInvitation]:
    """Create a new invitation; revoke any existing active invites for the same email+org."""
    # Revoke existing active invites
    if select is not None and hasattr(db, "execute"):
        try:
            rows = (
                (
                    await db.execute(
                        select(OrganizationInvitation).where(
                            OrganizationInvitation.org_id == org_id,
                            OrganizationInvitation.email == email,
                            OrganizationInvitation.used_at.is_(None),
                            OrganizationInvitation.revoked_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            now = datetime.now(timezone.utc)
            for r in rows:
                r.revoked_at = now
        except Exception:  # pragma: no cover
            pass
    else:
        # FakeDB path: revoke in-memory invites
        if hasattr(db, "added"):
            now = datetime.now(timezone.utc)
            for r in list(getattr(db, "added")):
                if (
                    isinstance(r, OrganizationInvitation)
                    and r.org_id == org_id
                    and r.email == email.lower().strip()
                    and r.used_at is None
                    and r.revoked_at is None
                ):
                    r.revoked_at = now

    raw = _new_token()
    inv = OrganizationInvitation(
        org_id=org_id,
        email=email.lower().strip(),
        role=role,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        created_by=created_by,
        last_sent_at=datetime.now(timezone.utc),
        resend_count=0,
    )
    if hasattr(db, "add"):
        db.add(inv)
        if hasattr(db, "flush"):
            await db.flush()
    return raw, inv


async def resend_invitation(db: Any, *, invitation: OrganizationInvitation) -> str:
    raw = _new_token()
    invitation.token_hash = _hash_token(raw)
    invitation.last_sent_at = datetime.now(timezone.utc)
    invitation.resend_count = (invitation.resend_count or 0) + 1
    if hasattr(db, "flush"):
        await db.flush()
    return raw


async def accept_invitation(
    db: Any,
    *,
    invitation: OrganizationInvitation,
    user_id: uuid.UUID,
) -> OrganizationMembership:
    now = datetime.now(timezone.utc)
    if invitation.revoked_at or invitation.used_at:
        raise ValueError("invitation_unusable")
    if invitation.expires_at and invitation.expires_at < now:
        raise ValueError("invitation_expired")

    # mark used
    invitation.used_at = now

    # create membership (upsert-like enforced by DB unique constraint)
    mem = OrganizationMembership(org_id=invitation.org_id, user_id=user_id, role=invitation.role)
    if hasattr(db, "add"):
        db.add(mem)
        if hasattr(db, "flush"):
            await db.flush()
    return mem


__all__ = [
    "issue_invitation",
    "resend_invitation",
    "accept_invitation",
]
