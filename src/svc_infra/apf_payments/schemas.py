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
