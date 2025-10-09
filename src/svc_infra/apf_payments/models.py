from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from svc_infra.db.sql.authref import user_fk, user_id_type
from svc_infra.db.sql.base import ModelBase


class PayCustomer(ModelBase):
    __tablename__ = "pay_customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Mandatory FK to the project’s actual auth table, with automatic type.
    user_id: Mapped[Optional[str]] = mapped_column(
        user_id_type(), user_fk("SET NULL"), index=True, nullable=True
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
        user_id_type(), user_fk("SET NULL"), index=True, nullable=True
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
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)  # compact JSON string


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
        user_id_type(), user_fk("SET NULL"), index=True, nullable=True
    )

    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # payment|refund|fee|payout...
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # pending|posted|void

    __table_args__ = (Index("ix_ledger_user_ts", "user_id", "ts"),)
