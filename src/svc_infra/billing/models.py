from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from svc_infra.db.sql.base import ModelBase

TENANT_ID_LEN = 64


class UsageEvent(ModelBase):
    __tablename__ = "billing_usage_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)
    metric: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    at_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "metric", "idempotency_key", name="uq_usage_idem"),
        Index("ix_usage_tenant_metric_ts", "tenant_id", "metric", "at_ts"),
    )


class UsageAggregate(ModelBase):
    __tablename__ = "billing_usage_aggregates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)
    metric: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granularity: Mapped[str] = mapped_column(String(8), nullable=False)  # hour|day|month
    total: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "metric", "period_start", "granularity", name="uq_usage_agg"),
    )


class Plan(ModelBase):
    __tablename__ = "billing_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class PlanEntitlement(ModelBase):
    __tablename__ = "billing_plan_entitlements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_per_window: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    window: Mapped[str] = mapped_column(String(8), nullable=False)  # day|month
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class Subscription(ModelBase):
    __tablename__ = "billing_subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)
    plan_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class Price(ModelBase):
    __tablename__ = "billing_prices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    unit_amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)  # minor units
    metric: Mapped[Optional[str]] = mapped_column(String(64))  # null for fixed recurring
    recurring_interval: Mapped[Optional[str]] = mapped_column(String(8))  # month|year
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class Invoice(ModelBase):
    __tablename__ = "billing_invoices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(TENANT_ID_LEN), index=True, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    total_amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    provider_invoice_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class InvoiceLine(ModelBase):
    __tablename__ = "billing_invoice_lines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    price_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    metric: Mapped[Optional[str]] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    amount: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
