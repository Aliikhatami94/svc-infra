from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID

_APIKEY_HMAC_SECRET = os.getenv("APIKEY_HASH_SECRET") or "change-me-low-entropy-dev"


def _hmac_sha256(s: str) -> str:
    return hmac.new(_APIKEY_HMAC_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApiKey(ModelBase):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Optional owner (bind key to a user). If null => service key.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    user = relationship("User", lazy="selectin")

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # We store only a hash + a short prefix for quick lookup/UX
    key_prefix: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # hex sha256

    scopes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)

    created_at = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("key_prefix", name="uq_apikey_prefix"),
        Index("ix_api_keys_user_id", "user_id"),
    )

    # Helpers
    @staticmethod
    def make_secret() -> tuple[str, str, str]:
        """
        Returns (plaintext, prefix, hash). The plaintext is shown ONCE to the caller.
        Format: ak_<prefix>_<random>
        """
        import base64
        import secrets

        prefix = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
        rand = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip("=")
        plaintext = f"ak_{prefix}_{rand}"
        return plaintext, prefix, _hmac_sha256(plaintext)

    @staticmethod
    def hash(plaintext: str) -> str:
        return _hmac_sha256(plaintext)

    def mark_used(self):
        self.last_used_at = _now()
