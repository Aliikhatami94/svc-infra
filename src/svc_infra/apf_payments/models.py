from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from svc_infra.db.sql.authref import user_fk_constraint, user_id_type
from svc_infra.db.sql.base import ModelBase

TENANT_ID_LEN = 64


class PayCustomer(ModelBase):
    __tablename__ = "pay_customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Tenant scoping
    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    # Always typed to match the actual auth PK; FK is enforced at table level
    user_id: Mapped[Optional[str]] = mapped_column(user_id_type(), index=True, nullable=True)

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        user_fk_constraint("user_id", ondelete="SET NULL"),
        Index("ix_pay_customers_user_provider", "user_id", "provider"),
        Index("ix_pay_customers_tenant_provider", "tenant_id", "provider"),
    )


class PayIntent(ModelBase):
    __tablename__ = "pay_intents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    user_id: Mapped[Optional[str]] = mapped_column(user_id_type(), index=True, nullable=True)

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_intent_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)  # minor units
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    client_secret: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    captured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        user_fk_constraint("user_id", ondelete="SET NULL"),
        Index("ix_pay_intents_user_provider", "user_id", "provider"),
        Index("ix_pay_intents_tenant_provider", "tenant_id", "provider"),
    )


class PayEvent(ModelBase):
    __tablename__ = "pay_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # compact JSON string


class LedgerEntry(ModelBase):
    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_ref: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(user_id_type(), index=True, nullable=True)
    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # payment|refund|fee|payout...
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # pending|posted|void

    __table_args__ = (
        user_fk_constraint("user_id", ondelete="SET NULL"),
        Index("ix_ledger_user_ts", "user_id", "ts"),
        Index("ix_ledger_tenant_provider", "tenant_id", "provider"),
        UniqueConstraint(
            "tenant_id",
            "provider",
            "provider_ref",
            "kind",
            name="uq_ledger_tenant_provider_ref_kind",
        ),
    )


class PayPaymentMethod(ModelBase):
    __tablename__ = "pay_methods"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    user_id: Mapped[Optional[str]] = mapped_column(user_id_type(), index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    provider_method_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    brand: Mapped[Optional[str]] = mapped_column(String(32))
    last4: Mapped[Optional[str]] = mapped_column(String(8))
    exp_month: Mapped[Optional[int]] = mapped_column(Numeric(2, 0))
    exp_year: Mapped[Optional[int]] = mapped_column(Numeric(4, 0))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        user_fk_constraint("user_id", ondelete="SET NULL"),
        Index(
            "ix_pay_methods_tenant_provider_customer",
            "tenant_id",
            "provider",
            "provider_customer_id",
        ),
    )


class PayProduct(ModelBase):
    __tablename__ = "pay_products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_product_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class PayPrice(ModelBase):
    __tablename__ = "pay_prices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_price_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    provider_product_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    unit_amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)  # minor units
    interval: Mapped[Optional[str]] = mapped_column(String(16))  # month|year|week|day
    trial_days: Mapped[Optional[int]] = mapped_column(Numeric(5, 0))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class PaySubscription(ModelBase):
    __tablename__ = "pay_subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    user_id: Mapped[Optional[str]] = mapped_column(user_id_type(), index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    provider_price_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # active|trialing|canceled|past_due|incomplete
    quantity: Mapped[int] = mapped_column(Numeric(10, 0), default=1, nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        user_fk_constraint("user_id", ondelete="SET NULL"),
        Index(
            "ix_pay_subscriptions_tenant_provider_customer",
            "tenant_id",
            "provider",
            "provider_customer_id",
        ),
    )


class PayInvoice(ModelBase):
    __tablename__ = "pay_invoices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    user_id: Mapped[Optional[str]] = mapped_column(user_id_type(), index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_invoice_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    provider_customer_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), index=True, nullable=False
    )  # draft|open|paid|void|uncollectible
    amount_due: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    hosted_invoice_url: Mapped[Optional[str]] = mapped_column(String(255))
    pdf_url: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        user_fk_constraint("user_id", ondelete="SET NULL"),
        Index(
            "ix_pay_invoices_tenant_provider_customer",
            "tenant_id",
            "provider",
            "provider_customer_id",
        ),
    )


class PaySetupIntent(ModelBase):
    __tablename__ = "pay_setup_intents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    user_id: Mapped[Optional[str]] = mapped_column(user_id_type(), index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_setup_intent_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # requires_action|succeeded|canceled|processing
    client_secret: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        user_fk_constraint("user_id", ondelete="SET NULL"),
        Index("ix_pay_setup_intents_tenant_provider", "tenant_id", "provider"),
    )


class PayDispute(ModelBase):
    __tablename__ = "pay_disputes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_dispute_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    provider_charge_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # needs_response|under_review|won|lost|warning_closed
    evidence_due_by: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class PayPayout(ModelBase):
    __tablename__ = "pay_payouts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)

    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider_payout_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # pending|in_transit|paid|canceled|failed
    arrival_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    type: Mapped[Optional[str]] = mapped_column(String(32))  # bank_account|card|...
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
