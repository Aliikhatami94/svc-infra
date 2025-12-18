"""Authentication module for svc-infra.

Provides user authentication, authorization, and security primitives.

Key exports:
- add_auth_users: Add authentication routes to FastAPI app
- Identity, OptionalIdentity: Annotated dependencies for auth
- RequireUser, RequireRoles, RequireScopes: Authorization guards
- Principal: Unified identity (user via JWT/cookie or service via API key)
- AuthSettings, get_auth_settings: Auth configuration
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# These imports are safe (no circular dependency)
from .policy import AuthPolicy, DefaultAuthPolicy
from .security import (
    Identity,
    OptionalIdentity,
    Principal,
    RequireAnyScope,
    RequireIdentity,
    RequireRoles,
    RequireScopes,
    RequireService,
    RequireUser,
)
from .settings import AuthSettings, JWTSettings, OIDCProvider, get_auth_settings

if TYPE_CHECKING:
    from .add import add_auth_users as add_auth_users

__all__ = [
    # Main setup
    "add_auth_users",
    # Identity/Auth guards
    "Identity",
    "OptionalIdentity",
    "Principal",
    "RequireIdentity",
    "RequireUser",
    "RequireService",
    "RequireRoles",
    "RequireScopes",
    "RequireAnyScope",
    # Policy
    "AuthPolicy",
    "DefaultAuthPolicy",
    # Settings
    "AuthSettings",
    "get_auth_settings",
    "JWTSettings",
    "OIDCProvider",
]


def __getattr__(name: str):
    """Lazy import for add_auth_users to avoid circular import."""
    if name == "add_auth_users":
        from .add import add_auth_users

        return add_auth_users
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
