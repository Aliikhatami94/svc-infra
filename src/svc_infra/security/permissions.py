from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Dict, Iterable, Set

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
        "admin.impersonate",
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


# ------- ABAC (Attribute-Based Access Control) helpers -------
ABACPredicate = Callable[[Identity, Any], bool | Awaitable[bool]]


def owns_resource(attr: str = "owner_id") -> ABACPredicate:
    def _predicate(principal: Identity, resource: Any) -> bool:
        user = getattr(principal, "user", None)
        uid = getattr(user, "id", None)
        rid = getattr(resource, attr, None) or getattr(resource, "user_id", None)
        return bool(uid is not None and rid is not None and str(uid) == str(rid))

    return _predicate


async def _maybe_await(v):
    if inspect.isawaitable(v):
        return await v
    return v


def enforce_abac(
    principal: Identity,
    *,
    permission: str,
    resource: Any,
    predicate: ABACPredicate,
):
    perms = principal_permissions(principal)
    if permission not in perms:
        raise HTTPException(403, f"missing_permissions:{permission}")
    ok = False
    # allow sync or async predicate
    res = predicate(principal, resource)
    if inspect.isawaitable(res):
        # Fast path for sync contexts: raise clear guidance
        raise RuntimeError(
            "enforce_abac received an async predicate in a sync context; use RequireABAC for FastAPI dependencies."
        )
    else:
        ok = bool(res)
    if not ok:
        raise HTTPException(403, "forbidden")
    return principal


def RequireABAC(
    *,
    permission: str,
    predicate: ABACPredicate,
    resource_getter: Callable[..., Any],
):
    """FastAPI dependency: enforce permission and attribute check using a resource provider.

    Example:
        def load_doc(): ...
        @router.get("/docs/{doc_id}", dependencies=[RequireABAC(permission="doc.read", predicate=owns_resource(), resource_getter=load_doc)])
        async def get_doc(identity: Identity, doc = Depends(load_doc)):
            ...
    Note: Using the provider in both the dependency and endpoint will call it twice. For heavy
    providers, wire only in the dependency and re-fetch via the dependency override or request.state.
    """

    async def _guard(principal: Identity, resource: Any = Depends(resource_getter)):
        perms = principal_permissions(principal)
        if permission not in perms:
            raise HTTPException(403, f"missing_permissions:{permission}")
        ok = await _maybe_await(predicate(principal, resource))
        if not ok:
            raise HTTPException(403, "forbidden")
        return principal

    return Depends(_guard)


__all__ = [
    "PERMISSION_REGISTRY",
    "get_permissions_for_roles",
    "principal_permissions",
    "has_permission",
    "RequirePermission",
    "RequireAnyPermission",
    "RequireABAC",
    "enforce_abac",
    "owns_resource",
]
