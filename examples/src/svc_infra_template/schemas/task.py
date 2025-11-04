from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Timestamped(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime


class TaskBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    name: str
    description: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)


class TaskRead(TaskBase, Timestamped):
    id: UUID


class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = None
    extra: Optional[Dict[str, Any]] = None
