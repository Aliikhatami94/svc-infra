from __future__ import annotations

from collections.abc import Callable
from typing import Any

_UserModel: type | None = None
_GetStrategy: Callable[[], Any] | None = None
_AuthPrefix: str = "/auth"
_UserScopeResolver: Callable[[Any], list[str]] | None = None


def set_auth_state(
    *, user_model: type, get_strategy: Callable[[], Any], auth_prefix: str = "/auth"
):
    global _UserModel, _GetStrategy, _AuthPrefix
    _UserModel = user_model
    _GetStrategy = get_strategy
    _AuthPrefix = auth_prefix


def get_auth_state() -> tuple[type, Callable[[], Any], str]:
    if _UserModel is None or _GetStrategy is None:
        raise RuntimeError("Auth state not initialized; call set_auth_state() in add_auth_users().")
    return _UserModel, _GetStrategy, _AuthPrefix


def set_user_scope_resolver(fn: Callable[[Any], list[str]]):
    global _UserScopeResolver
    _UserScopeResolver = fn


def get_user_scope_resolver() -> Callable[[Any], list[str]]:
    return _UserScopeResolver or (
        lambda u: getattr(u, "scopes", None) or getattr(u, "roles", []) or []
    )
