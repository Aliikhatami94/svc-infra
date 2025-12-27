"""Billing module for usage tracking, metering, and invoicing.

Primary API:
    AsyncBillingService - Async billing service

Models:
    UsageEvent, UsageAggregate, Invoice, InvoiceLine, Plan, Subscription, etc.

Example:
    from svc_infra.billing import AsyncBillingService

    service = AsyncBillingService(async_session, tenant_id)
    await service.record_usage(metric="api_calls", amount=1, ...)
"""

from .async_service import AsyncBillingService
from .models import (
    Invoice,
    InvoiceLine,
    Plan,
    PlanEntitlement,
    Price,
    Subscription,
    UsageAggregate,
    UsageEvent,
)

__all__ = [
    # Primary API
    "AsyncBillingService",
    # Models
    "UsageEvent",
    "UsageAggregate",
    "Plan",
    "PlanEntitlement",
    "Subscription",
    "Price",
    "Invoice",
    "InvoiceLine",
]
