"""
Utilities for capturing routers from add_* functions for versioned routing.

This module provides helpers to use integration functions (add_banking, add_payments, etc.)
under versioned routing without creating separate documentation cards.

See: svc-infra/docs/versioned-integrations.md
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar
from unittest.mock import patch

from fastapi import APIRouter, FastAPI

__all__ = ["extract_router"]

T = TypeVar("T")


def extract_router(
    add_function: Callable[..., T],
    *,
    prefix: str,
    **kwargs: Any,
) -> tuple[APIRouter, T]:
    """
    Capture the router from an add_* function for versioned mounting.

    This allows you to use integration functions like add_banking(), add_payments(),
    etc. under versioned routing (e.g., /v0/banking) without creating separate
    documentation cards.

    Args:
        add_function: The add_* function to capture from (e.g., add_banking)
        prefix: URL prefix for the routes (e.g., "/banking")
        **kwargs: Arguments to pass to the add_function

    Returns:
        Tuple of (router, return_value) where:
        - router: The captured APIRouter with all routes
        - return_value: The original return value from add_function (e.g., provider instance)

    Example:
        ```python
        # In routers/v0/banking.py
        from svc_infra.api.fastapi.versioned import extract_router
        from fin_infra.banking import add_banking

        router, banking_provider = extract_router(
            add_banking,
            prefix="/banking",
            provider="plaid",
            cache_ttl=60,
        )

        # svc-infra auto-discovers 'router' and mounts at /v0/banking
        ```

    Pattern:
        1. Creates a mock FastAPI app
        2. Intercepts include_router to capture the router
        3. Patches add_prefixed_docs to prevent separate card creation
        4. Calls the add_function which creates all routes
        5. Returns the captured router for auto-discovery

    See Also:
        - docs/versioned-integrations.md: Full pattern documentation
        - api/fastapi/dual/public.py: Similar pattern for dual routers
    """
    # Create mock app to capture router
    mock_app = FastAPI()
    captured_router: APIRouter | None = None

    def _capture_router(router: APIRouter, **_kwargs: Any) -> None:
        """Intercept include_router to capture instead of mount."""
        nonlocal captured_router
        captured_router = router

    mock_app.include_router = _capture_router  # type: ignore[assignment]

    # Patch add_prefixed_docs to prevent separate card (no-op if function doesn't call it)
    def _noop_docs(*args: Any, **kwargs: Any) -> None:
        pass

    # Call add_function with patches active
    with patch("svc_infra.api.fastapi.docs.scoped.add_prefixed_docs", _noop_docs):
        result = add_function(
            mock_app,
            prefix=prefix,
            **kwargs,
        )

    if captured_router is None:
        raise RuntimeError(
            f"Failed to capture router from {add_function.__name__}. "
            f"The function may not call app.include_router()."
        )

    return captured_router, result
