from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from svc_infra.db.sql.base import ModelBase


class PayCustomer(ModelBase, table=True, table_name="pay_customers"):
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_customer_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (Index("ix_pay_customers_user_provider", "user_id", "provider"),)


class PayIntent(ModelBase, table=True, table_name="pay_intents"):
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_intent_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    amount: Mapped[int] = mapped_column(Numeric(18, 0))  # store in minor units
    currency: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(32), index=True)
    client_secret: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    captured: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_pay_intents_user_provider", "user_id", "provider"),)


class PayEvent(ModelBase, table=True, table_name="pay_events"):
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    payload_json: Mapped[str] = mapped_column(String)  # compact JSON string


class LedgerEntry(ModelBase, table=True, table_name="ledger_entries"):
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_ref: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    amount: Mapped[int] = mapped_column(Numeric(18, 0))
    currency: Mapped[str] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(24))  # payment|refund|fee|payout...
    status: Mapped[str] = mapped_column(String(24))  # pending|posted|void

    __table_args__ = (Index("ix_ledger_user_ts", "user_id", "ts"),)
