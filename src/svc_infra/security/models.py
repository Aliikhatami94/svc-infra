from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID

# ----------------------------- Models -----------------------------------------


class AuthSession(ModelBase):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[Optional[str]] = mapped_column(Text)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )

    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class RefreshToken(ModelBase):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("auth_sessions.id", ondelete="CASCADE"), index=True
    )
    session: Mapped[AuthSession] = relationship(back_populates="refresh_tokens")

    token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (UniqueConstraint("token_hash", name="uq_refresh_token_hash"),)


class RefreshTokenRevocation(ModelBase):
    __tablename__ = "refresh_token_revocations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)


class FailedAuthAttempt(ModelBase):
    __tablename__ = "failed_auth_attempts"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("ix_failed_attempt_user_time", "user_id", "ts"),)


class RolePermission(ModelBase):
    __tablename__ = "role_permissions"

    role: Mapped[str] = mapped_column(String(64), primary_key=True)
    permission: Mapped[str] = mapped_column(String(128), primary_key=True)


class AuditLog(ModelBase):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_ref: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    prev_hash: Mapped[Optional[str]] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    __table_args__ = (Index("ix_audit_chain", "tenant_id", "id"),)


# ------------------------ Org / Teams ----------------------------------------


class Organization(ModelBase):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class Team(ModelBase):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class OrganizationMembership(ModelBase):
    __tablename__ = "organization_memberships"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_org_user_membership"),)


class OrganizationInvitation(ModelBase):
    __tablename__ = "organization_invitations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resend_count: Mapped[int] = mapped_column(default=0)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ------------------------ OAuth Provider Accounts -----------------------------
# MOVED to svc_infra.security.oauth_models for opt-in OAuth support
# Projects that enable OAuth should import ProviderAccount from there


# ------------------------ Utilities -------------------------------------------


def generate_refresh_token() -> str:
    """Generate a random refresh token (opaque)."""
    return uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_audit_hash(
    prev_hash: Optional[str],
    *,
    ts: datetime,
    actor_id: Optional[uuid.UUID],
    tenant_id: Optional[str],
    event_type: str,
    resource_ref: Optional[str],
    metadata: dict,
) -> str:
    """Compute SHA256 hash chaining previous hash + canonical event payload."""
    prev = prev_hash or "0" * 64
    payload = {
        "ts": ts.isoformat(),
        "actor_id": str(actor_id) if actor_id else None,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "resource_ref": resource_ref,
        "metadata": metadata,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev + canonical).encode()).hexdigest()


def rotate_refresh_token(
    current_hash: str, *, ttl_minutes: int = 10080
) -> tuple[str, str, datetime]:
    """Rotate: returns (new_raw, new_hash, expires_at)."""
    new_raw = generate_refresh_token()
    new_hash = hash_refresh_token(new_raw)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    return new_raw, new_hash, expires_at


__all__ = [
    "AuthSession",
    "RefreshToken",
    "RefreshTokenRevocation",
    "FailedAuthAttempt",
    "RolePermission",
    "AuditLog",
    "Organization",
    "Team",
    "OrganizationMembership",
    "OrganizationInvitation",
    # ProviderAccount moved to svc_infra.security.oauth_models (opt-in)
    "generate_refresh_token",
    "hash_refresh_token",
    "compute_audit_hash",
    "rotate_refresh_token",
]
