from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID


# ----- config (shared with scaffold) ------------------------------------------
# Single source of truth for the auth table name.
# You can set AUTH_TABLE_NAME in your .env. We also accept legacy aliases.
def _resolve_auth_table_name() -> str:
    for key in ("AUTH_TABLE_NAME", "SVC_INFRA_AUTH_TABLE", "APF_AUTH_TABLE_NAME"):
        val = os.getenv(key)
        if val and val.strip():
            return val.strip()
    return "users"  # default


_AUTH_TABLE = _resolve_auth_table_name()

# Optional: enforce a real FK to the auth table (defaults to soft-link only).
# If you enable this, we assume the auth PK type is GUID() (matches svc-infra auth template).
# If your auth PK is not a GUID, set AUTH_USER_ID_TYPE=string and we’ll use String(64) instead.
_ENFORCE_FK = os.getenv("APF_PAYMENTS_USER_FK", "0").lower() in {"1", "true", "yes"}

_USER_ID_KIND = (os.getenv("AUTH_USER_ID_TYPE") or "guid").lower()  # "guid" | "string"
if _USER_ID_KIND not in {"guid", "string"}:
    _USER_ID_KIND = "guid"


def _user_id_type():
    return GUID() if _USER_ID_KIND == "guid" else String(64)


def _user_fk_arg():
    if not _ENFORCE_FK:
        return tuple()
    return (ForeignKey(f"{_AUTH_TABLE}.id", ondelete="SET NULL"),)


# -----------------------------------------------------------------------------


class PayCustomer(ModelBase):
    __tablename__ = "pay_customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Conditionally-typed + optional FK to users table
    user_id: Mapped[Optional[str]] = mapped_column(
        _user_id_type(), *_user_fk_arg(), index=True, nullable=True
    )

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    __table_args__ = (Index("ix_pay_customers_user_provider", "user_id", "provider"),)


class PayIntent(ModelBase):
    __tablename__ = "pay_intents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    user_id: Mapped[Optional[str]] = mapped_column(
        _user_id_type(), *_user_fk_arg(), index=True, nullable=True
    )

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_intent_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)  # minor units
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    client_secret: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    captured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (Index("ix_pay_intents_user_provider", "user_id", "provider"),)


class PayEvent(ModelBase):
    __tablename__ = "pay_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    # compact JSON string payload; String() (no length) -> TEXT on PG
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class LedgerEntry(ModelBase):
    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_ref: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        _user_id_type(), *_user_fk_arg(), index=True, nullable=True
    )
    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # payment|refund|fee|payout...
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # pending|posted|void

    __table_args__ = (Index("ix_ledger_user_ts", "user_id", "ts"),)
