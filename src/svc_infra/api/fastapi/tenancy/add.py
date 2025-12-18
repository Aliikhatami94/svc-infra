from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from .context import set_tenant_resolver


def add_tenancy(app: FastAPI, *, resolver: Callable[..., Any] | None = None) -> None:
    """Wire tenancy resolver for the application.

    Provide a resolver(request, identity, header) -> Optional[str] to override
    the default resolution. Pass None to clear a previous override.
    """
    set_tenant_resolver(resolver)


__all__ = ["add_tenancy"]
