from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import FastAPI

from .context import set_tenant_resolver


def add_tenancy(app: FastAPI, *, resolver: Optional[Callable[..., Any]] = None) -> None:
    """Wire tenancy resolver for the application.

    Provide a resolver(request, identity, header) -> Optional[str] to override
    the default resolution. Pass None to clear a previous override.
    """
    set_tenant_resolver(resolver)


__all__ = ["add_tenancy"]
