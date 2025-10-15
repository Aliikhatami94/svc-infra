from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from .add import add_webhooks

__all__ = ["add_webhooks"]


def __getattr__(name: str):
    if name == "add_webhooks":
        from .add import add_webhooks

        return add_webhooks
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
