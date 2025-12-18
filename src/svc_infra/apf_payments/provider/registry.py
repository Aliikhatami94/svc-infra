from __future__ import annotations

from ..settings import get_payments_settings
from .base import ProviderAdapter


class ProviderRegistry:
    def __init__(self):
        self._adapters: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter):
        self._adapters[adapter.name] = adapter

    def get(self, name: str | None = None) -> ProviderAdapter:
        settings = get_payments_settings()
        key = (name or settings.default_provider).lower()
        if key not in self._adapters:
            raise RuntimeError(f"No payments adapter registered for '{key}'")
        return self._adapters[key]


_REGISTRY: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ProviderRegistry()
    return _REGISTRY
