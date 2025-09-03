from __future__ import annotations
from typing import Optional, Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class Timestamped(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime

class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    tenant_id: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    mfa_enabled: bool = False
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="extra")  # <-- matches model.extra

class UserRead(UserBase, Timestamped):
    id: str
    last_login: Optional[datetime] = None
    disabled_reason: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    tenant_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
    tenant_id: Optional[str] = None
    roles: Optional[List[str]] = None
    mfa_enabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    disabled_reason: Optional[str] = None

class UserPasswordUpdate(BaseModel):
    current_password: Optional[str] = None
    new_password: str = Field(min_length=8)