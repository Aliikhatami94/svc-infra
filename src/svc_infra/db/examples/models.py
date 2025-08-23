from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, UUIDMixin, TimestampMixin


class Widget(UUIDMixin, TimestampMixin, Base):
    """Copy-pasteable example model.

    - UUID primary key via UUIDMixin
    - created_at/updated_at via TimestampMixin
    """

    __tablename__ = "widgets"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)

