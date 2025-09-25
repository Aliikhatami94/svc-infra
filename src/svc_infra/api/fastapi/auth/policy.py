from __future__ import annotations

from typing import Any, Protocol


class AuthPolicy(Protocol):

    async def should_require_mfa(self, user: Any) -> bool:
        pass

    async def on_login_success(self, user: Any) -> None:
        pass

    async def on_mfa_challenge(self, user: Any) -> None:
        pass


class DefaultAuthPolicy:
    def __init__(self, settings):
        self.settings = settings

    async def should_require_mfa(self, user: Any) -> bool:
        # default: user-level only; projects can override (tenant/global)
        return bool(getattr(user, "mfa_enabled", False))

    async def on_login_success(self, user: Any) -> None:
        # no-op; projects can update last_login, audit, etc.
        return None

    async def on_mfa_challenge(self, user: Any) -> None:
        # no-op; projects can audit challenges
        return None
