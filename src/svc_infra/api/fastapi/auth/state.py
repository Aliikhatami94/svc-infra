from __future__ import annotations

from typing import Any, Callable, Optional

_UserModel: Optional[type] = None
_GetStrategy: Optional[Callable[[], Any]] = None
_AuthPrefix: str = "/auth"
_UserScopeResolver: Optional[Callable[[Any], list[str]]] = None


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
