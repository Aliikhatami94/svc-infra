from __future__ import annotations

from typing import Any

from .dual_router import DualAPIRouter


def public_router(**kwargs: Any) -> DualAPIRouter:
    return DualAPIRouter(**kwargs)
