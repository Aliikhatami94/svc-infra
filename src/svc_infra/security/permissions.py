from __future__ import annotations

from typing import Dict, Iterable, Set

from fastapi import Depends, HTTPException

from svc_infra.api.fastapi.auth.security import Identity

# Central role -> permissions mapping. Projects can extend at startup.
PERMISSION_REGISTRY: Dict[str, Set[str]] = {
    "admin": {
        "user.read",
        "user.write",
        "billing.read",
        "billing.write",
        "security.session.revoke",
        "security.session.list",
    },
    "support": {"user.read", "billing.read"},
    "auditor": {"user.read", "billing.read", "audit.read"},
}


def get_permissions_for_roles(roles: Iterable[str]) -> Set[str]:
    perms: Set[str] = set()
    for r in roles:
        perms |= PERMISSION_REGISTRY.get(r, set())
    return perms


def principal_permissions(principal: Identity) -> Set[str]:
    roles = getattr(principal.user, "roles", []) or []
    return get_permissions_for_roles(roles)


def has_permission(principal: Identity, permission: str) -> bool:
    return permission in principal_permissions(principal)


def RequirePermission(*needed: str):
    """FastAPI dependency enforcing all listed permissions are present."""

    async def _guard(principal: Identity):
        perms = principal_permissions(principal)
        missing = [p for p in needed if p not in perms]
        if missing:
            raise HTTPException(403, f"missing_permissions:{','.join(missing)}")
        return principal

    return Depends(_guard)


def RequireAnyPermission(*candidates: str):
    async def _guard(principal: Identity):
        perms = principal_permissions(principal)
        if not (perms & set(candidates)):
            raise HTTPException(403, "insufficient_permissions")
        return principal

    return Depends(_guard)


__all__ = [
    "PERMISSION_REGISTRY",
    "get_permissions_for_roles",
    "principal_permissions",
    "has_permission",
    "RequirePermission",
    "RequireAnyPermission",
]
