from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from svc_infra.app.env import require_secret
from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID


def _get_apikey_secret() -> str:
    """Get APIKEY_HASH_SECRET, requiring it in production."""
    return require_secret(
        os.getenv("APIKEY_HASH_SECRET"),
        "APIKEY_HASH_SECRET",
        dev_default="dev-only-apikey-hmac-secret-not-for-production",
    )


def _hmac_sha256(s: str) -> str:
    secret = _get_apikey_secret()
    return hmac.new(secret.encode(), s.encode(), hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


# -------------------- Factory & registry --------------------

_ApiKeyModel: type | None = None


def get_apikey_model() -> type:
    """Return the bound ApiKey model (or raise if not enabled)."""
    if _ApiKeyModel is None:
        raise RuntimeError("ApiKey model is not enabled. Call bind_apikey_model(...) first.")
    return _ApiKeyModel


def bind_apikey_model(user_model: type[ModelBase], *, table_name: str = "api_keys") -> type:
    """
    Create and register an ApiKey model bound to the provided user_model and table name.
    Call this once during app boot (e.g., inside add_auth_users when enable_api_keys=True).
    """

    class ApiKey(ModelBase):
        __tablename__ = table_name

        id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

        @declared_attr
        def user_id(cls) -> Mapped[uuid.UUID | None]:
            return mapped_column(
                GUID(),
                ForeignKey(f"{user_model.__tablename__}.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            )

        @declared_attr
        def user(cls):
            return relationship(user_model.__name__, lazy="selectin")

        name: Mapped[str] = mapped_column(String(128), nullable=False)

        # hash + short prefix for lookup
        key_prefix: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
        key_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # hex sha256

        scopes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
        active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
        expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        meta: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)

        created_at = mapped_column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
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
            Returns (plaintext, prefix, hash). plaintext is shown ONCE to the caller.
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

    global _ApiKeyModel
    _ApiKeyModel = ApiKey
    return ApiKey


def try_autobind_apikey_model(*, require_env: bool = False) -> type | None:
    """
    If API keys aren’t bound yet, try to discover the User model and bind.
    - If require_env=True, only bind when AUTH_ENABLE_API_KEYS is truthy.
    """
    global _ApiKeyModel
    if _ApiKeyModel is not None:
        return _ApiKeyModel

    if require_env:
        flag = os.getenv("AUTH_ENABLE_API_KEYS", "")
        if str(flag).strip().lower() not in {"1", "true", "yes"}:
            return None

    try:
        from svc_infra.db.sql.base import ModelBase

        # SQLAlchemy 2.x: iterate registry mappers to get mapped classes
        for mapper in list(ModelBase.registry.mappers):
            cls = mapper.class_
            if getattr(cls, "__svc_infra_auth_user__", False):
                return bind_apikey_model(cls)  # binds and returns ApiKey
    except Exception:
        return None

    return None
