from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Timestamped(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime


class TaskBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    name: str
    description: str | None = None
    tenant_id: str | None = None
    is_active: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class TaskRead(TaskBase, Timestamped):
    id: UUID


class TaskCreate(BaseModel):
    name: str
    description: str | None = None
    tenant_id: str | None = None
    is_active: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tenant_id: str | None = None
    is_active: bool | None = None
    extra: dict[str, Any] | None = None
