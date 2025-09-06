from __future__ import annotations
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    String, Boolean, DateTime, JSON, Text, func, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.mutable import MutableDict, MutableList  # <-- add

from svc_infra.db.setup.base import ModelBase

class User(ModelBase):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # auth state
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    disabled_reason: Mapped[Optional[str]] = mapped_column(Text)

    # org / roles / mfa
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    roles: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # misc (avoid attr name 'metadata' clash)
    extra: Mapped[dict] = mapped_column("metadata", MutableDict.as_mutable(JSON), default=dict)

    # auditing (DB-side timestamps)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"

# define functional index *after* class definition
Index("ix_users_email_lower", func.lower(User.email))