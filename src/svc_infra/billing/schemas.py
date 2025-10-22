from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, conint


class UsageIn(BaseModel):
    metric: str = Field(..., min_length=1, max_length=64)
    amount: conint(ge=0) = Field(..., description="Non-negative amount for the metric")
    at: Optional[datetime] = Field(
        default=None, description="Event timestamp (UTC). Defaults to server time if omitted."
    )
    idempotency_key: str = Field(..., min_length=1, max_length=128)
    metadata: dict = Field(default_factory=dict)


class UsageAckOut(BaseModel):
    id: str
    accepted: bool = True


class UsageAggregateRow(BaseModel):
    period_start: datetime
    granularity: str
    metric: str
    total: int


class UsageAggregatesOut(BaseModel):
    items: list[UsageAggregateRow] = Field(default_factory=list)
    next_cursor: Optional[str] = None
