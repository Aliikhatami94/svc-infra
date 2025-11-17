"""
OAuth provider account models (opt-in).

These models are only registered when a project explicitly enables OAuth.
Import this module only when enable_oauth=True is passed to add_auth_users.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID

if TYPE_CHECKING:
    from svc_infra.security.models import User


class ProviderAccount(ModelBase):
    """OAuth provider account linking (Google, GitHub, etc.)."""

    __tablename__ = "provider_accounts"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    raw_claims: Mapped[Optional[dict]] = mapped_column(JSON)

    # Bidirectional relationship to User model
    user: Mapped["User"] = relationship(back_populates="provider_accounts")

    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_provider_account"),
        Index("ix_provider_accounts_user_provider", "user_id", "provider"),
    )


__all__ = ["ProviderAccount"]
