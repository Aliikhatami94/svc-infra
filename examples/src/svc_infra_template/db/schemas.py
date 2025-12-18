"""Pydantic schemas for API serialization/validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

# ============================================================================
# Project Schemas
# ============================================================================


class ProjectBase(BaseModel):
    """Base project fields."""

    name: str
    description: str | None = None
    owner_email: EmailStr
    is_active: bool = True


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project (all fields optional)."""

    name: str | None = None
    description: str | None = None
    owner_email: EmailStr | None = None
    is_active: bool | None = None


class ProjectRead(ProjectBase):
    """Schema for reading a project (includes metadata)."""

    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Task Schemas
# ============================================================================


class TaskBase(BaseModel):
    """Base task fields."""

    title: str
    description: str | None = None
    status: str = "pending"
    project_id: int | None = None
    assigned_to: str | None = None
    completed_at: datetime | None = None


class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task (all fields optional)."""

    title: str | None = None
    description: str | None = None
    status: str | None = None
    project_id: int | None = None
    assigned_to: str | None = None
    completed_at: datetime | None = None


class TaskRead(TaskBase):
    """Schema for reading a task (includes metadata)."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
