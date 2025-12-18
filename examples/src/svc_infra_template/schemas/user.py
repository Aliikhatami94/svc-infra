from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi_users.schemas import BaseUser, BaseUserCreate, BaseUserUpdate
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ------------------------------ Base mixin ------------------------------------


class Timestamped(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime


# ------------------------------ ProviderAccount -------------------------------


class ProviderAccountBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider: str = Field(
        ..., json_schema_extra={"examples": ["google", "github", "linkedin", "microsoft"]}
    )
    provider_account_id: str


class ProviderAccountRead(ProviderAccountBase, Timestamped):
    id: UUID


# Note: provider accounts are created server-side during OAuth callback.

# ------------------------------ User ---------------------------------


# (Optional helper; keep if used elsewhere)
class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    mfa_enabled: bool = False
    metadata: dict[str, Any] | None = Field(default=None, alias="extra")  # matches model.extra


class UserRead(BaseUser[UUID], Timestamped):
    # BaseUser[UUID] already provides: id, email, is_active, is_superuser, is_verified
    full_name: str | None = None
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    mfa_enabled: bool = False
    metadata: dict[str, Any] | None = Field(default=None, alias="extra")
    provider_accounts: list[ProviderAccountRead] = Field(default_factory=list)
    last_login: datetime | None = None
    disabled_reason: str | None = None


class UserCreate(BaseUserCreate):
    # BaseUserCreate already has: email, password
    full_name: str | None = None
    tenant_id: str | None = None
    metadata: dict[str, Any] | None = None


class UserUpdate(BaseUserUpdate):
    # BaseUserUpdate already has: email?, password?
    full_name: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    is_verified: bool | None = None
    tenant_id: str | None = None
    roles: list[str] | None = None
    mfa_enabled: bool | None = None
    metadata: dict[str, Any] | None = None
    disabled_reason: str | None = None


class UserPasswordUpdate(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8)
