from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column


class Versioned:
    """Mixin for optimistic locking with integer version.

    - Initialize version=1 on insert (via default=1)
    - Bump version in app code before commit to detect mismatches.
    """

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
