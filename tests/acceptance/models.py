"""
Minimal User model for acceptance tests.

The security models (AuditLog, AuthSession, etc.) have foreign keys to 'users' table,
so we need to provide a User model for migrations to work.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID

if TYPE_CHECKING:
    pass


class User(ModelBase):
    """Minimal User model to satisfy security models' FK constraints."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


# Export metadata AFTER defining models so env.py can discover it with User table included
metadata = ModelBase.metadata
