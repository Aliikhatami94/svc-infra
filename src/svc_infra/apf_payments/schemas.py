from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, conint, constr

Currency = constr(pattern=r"^[A-Z]{3}$")
AmountMinor = conint(ge=0)  # minor units (cents)


class CustomerUpsertIn(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


class CustomerOut(BaseModel):
    id: str
    provider: str
    provider_customer_id: str
    email: Optional[str] = None
    name: Optional[str] = None


class IntentCreateIn(BaseModel):
    amount: AmountMinor = Field(..., description="Minor units (e.g., cents)")
    currency: Currency = Field(..., example="USD")
    description: Optional[str] = None
    capture_method: Literal["automatic", "manual"] = "automatic"
    payment_method_types: list[str] = Field(default_factory=list)  # let provider default


class NextAction(BaseModel):
    type: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class IntentOut(BaseModel):
    id: str
    provider: str
    provider_intent_id: str
    status: str
    amount: AmountMinor
    currency: Currency
    client_secret: Optional[str] = None
    next_action: Optional[NextAction] = None


class RefundIn(BaseModel):
    amount: Optional[AmountMinor] = None
    reason: Optional[str] = None


class TransactionRow(BaseModel):
    id: str
    ts: str
    type: Literal["payment", "refund", "fee", "payout"]
    amount: int
    currency: Currency
    status: str
    provider: str
    provider_ref: str
    user_id: Optional[str] = None
    net: Optional[int] = None
    fee: Optional[int] = None


class StatementRow(BaseModel):
    period_start: str
    period_end: str
    currency: Currency
    gross: int
    refunds: int
    fees: int
    net: int
    count: int


class PaymentMethodAttachIn(BaseModel):
    customer_provider_id: str
    payment_method_token: str  # provider token (e.g., stripe pm_ or payment_method id)
    make_default: bool = True


class PaymentMethodOut(BaseModel):
    id: str
    provider: str
    provider_customer_id: str
    provider_method_id: str
    brand: Optional[str] = None
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool = False


class ProductCreateIn(BaseModel):
    name: str
    active: bool = True


class ProductOut(BaseModel):
    id: str
    provider: str
    provider_product_id: str
    name: str
    active: bool


class PriceCreateIn(BaseModel):
    provider_product_id: str
    currency: Currency
    unit_amount: AmountMinor
    interval: Optional[Literal["day", "week", "month", "year"]] = None
    trial_days: Optional[int] = None
    active: bool = True


class PriceOut(BaseModel):
    id: str
    provider: str
    provider_price_id: str
    provider_product_id: str
    currency: Currency
    unit_amount: AmountMinor
    interval: Optional[str] = None
    trial_days: Optional[int] = None
    active: bool = True


class SubscriptionCreateIn(BaseModel):
    customer_provider_id: str
    price_provider_id: str
    quantity: int = 1
    trial_days: Optional[int] = None
    proration_behavior: Literal["create_prorations", "none", "always_invoice"] = "create_prorations"


class SubscriptionUpdateIn(BaseModel):
    price_provider_id: Optional[str] = None
    quantity: Optional[int] = None
    cancel_at_period_end: Optional[bool] = None
    proration_behavior: Literal["create_prorations", "none", "always_invoice"] = "create_prorations"


class SubscriptionOut(BaseModel):
    id: str
    provider: str
    provider_subscription_id: str
    provider_price_id: str
    status: str
    quantity: int
    cancel_at_period_end: bool
    current_period_end: Optional[str] = None


class InvoiceCreateIn(BaseModel):
    customer_provider_id: str
    auto_advance: bool = True


class InvoiceOut(BaseModel):
    id: str
    provider: str
    provider_invoice_id: str
    provider_customer_id: str
    status: str
    amount_due: AmountMinor
    currency: Currency
    hosted_invoice_url: Optional[str] = None
    pdf_url: Optional[str] = None
