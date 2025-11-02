"""Example database models showcasing svc-infra patterns."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from svc_infra_template.db.base import Base, SoftDeleteMixin, TimestampMixin


class Project(Base, TimestampMixin, SoftDeleteMixin):
    """
    Example Project model.

    Demonstrates:
    - TimestampMixin: Auto-managed created_at/updated_at
    - SoftDeleteMixin: Soft delete with deleted_at
    - Type-safe columns with Mapped[]
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Status tracking
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name!r})>"


class Task(Base, TimestampMixin):
    """
    Example Task model.

    Demonstrates:
    - Basic model without soft delete
    - Enum-like status field
    - Optional fields
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status: 'pending', 'in_progress', 'completed', 'cancelled'
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    # Optional: Link to project (in a real app, use foreign key)
    project_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Completion tracking
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title!r}, status={self.status})>"


# To use these models:
# 1. Run: python -m svc_infra.db init --project-root .
# 2. Run: python -m svc_infra.db revision -m "Initial models" --project-root .
# 3. Run: python -m svc_infra.db upgrade head --project-root .
