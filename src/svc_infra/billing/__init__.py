"""Billing module for usage tracking, metering, and invoicing.

Primary API:
    AsyncBillingService - Async billing service (recommended)

Deprecated:
    BillingService - Sync billing service (use AsyncBillingService instead)

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
from .service import BillingService  # Deprecated - kept for backward compatibility

__all__ = [
    # Primary API (recommended)
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
    # Deprecated (use AsyncBillingService instead)
    "BillingService",
]
