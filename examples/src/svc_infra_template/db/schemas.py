"""Pydantic schemas for API serialization/validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

# ============================================================================
# Project Schemas
# ============================================================================


class ProjectBase(BaseModel):
    """Base project fields."""

    name: str
    description: Optional[str] = None
    owner_email: EmailStr
    is_active: bool = True


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    owner_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class ProjectRead(ProjectBase):
    """Schema for reading a project (includes metadata)."""

    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Task Schemas
# ============================================================================


class TaskBase(BaseModel):
    """Base task fields."""

    title: str
    description: Optional[str] = None
    status: str = "pending"
    project_id: Optional[int] = None
    assigned_to: Optional[str] = None
    completed_at: Optional[datetime] = None


class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task (all fields optional)."""

    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[int] = None
    assigned_to: Optional[str] = None
    completed_at: Optional[datetime] = None


class TaskRead(TaskBase):
    """Schema for reading a task (includes metadata)."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
