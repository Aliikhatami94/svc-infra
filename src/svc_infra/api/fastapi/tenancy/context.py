from __future__ import annotations

from typing import Annotated, Any, Callable, Optional

from fastapi import Depends, HTTPException, Request

try:  # optional import; auth may not be used by all consumers
    from svc_infra.api.fastapi.auth.security import OptionalIdentity
except Exception:  # pragma: no cover - fallback for minimal builds
    OptionalIdentity = None  # type: ignore


_tenant_resolver: Optional[Callable[..., Any]] = None


def set_tenant_resolver(
    fn: Optional[Callable[..., Any]],
) -> None:
    """Set or clear a global override hook for tenant resolution.

    The function receives (request, identity, tenant_header) and should return a tenant id
    string or None to fall back to default logic.
    """
    global _tenant_resolver
    _tenant_resolver = fn


async def _maybe_await(x):
    if callable(getattr(x, "__await__", None)):
        return await x  # type: ignore[misc]
    return x


async def resolve_tenant_id(
    request: Request,
    tenant_header: Optional[str] = None,
    identity: Any = Depends(OptionalIdentity) if OptionalIdentity else None,  # type: ignore[arg-type]
) -> Optional[str]:
    """Resolve tenant id from override, identity, header, or request.state.

    Order:
      1) Global override hook (set_tenant_resolver)
      2) Auth identity: user.tenant_id then api_key.tenant_id (if available)
      3) X-Tenant-Id header
      4) request.state.tenant_id
    """
    # read header value if not provided directly (supports direct calls without DI)
    if tenant_header is None:
        try:
            tenant_header = request.headers.get("X-Tenant-Id")  # type: ignore[assignment]
        except Exception:
            tenant_header = None

    # 1) global override
    if _tenant_resolver is not None:
        try:
            v = _tenant_resolver(request, identity, tenant_header)
            v2 = await _maybe_await(v)
            if v2:
                return str(v2)
        except Exception:
            # fall through to defaults
            pass

    # 2) from identity
    try:
        if identity and getattr(identity, "user", None) is not None:
            tid = getattr(identity.user, "tenant_id", None)
            if tid:
                return str(tid)
        if identity and getattr(identity, "api_key", None) is not None:
            tid = getattr(identity.api_key, "tenant_id", None)
            if tid:
                return str(tid)
    except Exception:
        pass

    # 3) from header
    if tenant_header and isinstance(tenant_header, str) and tenant_header.strip():
        return tenant_header.strip()

    # 4) request.state
    try:
        st_tid = getattr(getattr(request, "state", object()), "tenant_id", None)
        if st_tid:
            return str(st_tid)
    except Exception:
        pass

    return None


async def require_tenant_id(
    tenant_id: Optional[str] = Depends(resolve_tenant_id),
) -> str:
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_context_missing")
    return tenant_id


# DX aliases
TenantId = Annotated[str, Depends(require_tenant_id)]
OptionalTenantId = Annotated[Optional[str], Depends(resolve_tenant_id)]


__all__ = [
    "TenantId",
    "OptionalTenantId",
    "resolve_tenant_id",
    "require_tenant_id",
    "set_tenant_resolver",
]
