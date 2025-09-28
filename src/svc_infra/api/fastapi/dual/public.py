from __future__ import annotations

from typing import Any

from ..openapi.apply import apply_default_responses, apply_default_security
from ..openapi.responses import DEFAULT_PUBLIC
from .router import DualAPIRouter


def public_router(**kwargs: Any) -> DualAPIRouter:
    """
    Public router: no auth dependencies.
    - Marks operations as public in OpenAPI (no lock icon) via security: []
    - Attaches standard reusable responses for public endpoints
    """
    r = DualAPIRouter(**kwargs)

    # Keep OpenAPI consistent with the other router factories
    apply_default_security(r, default_security=[])
    apply_default_responses(r, DEFAULT_PUBLIC)

    return r
