from __future__ import annotations

import base64
import hmac
import inspect
import json
import logging
import os
import time
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ....app.env import get_current_environment
from ....security.permissions import RequirePermission
from ..auth.security import Identity, Principal, _current_principal
from ..auth.state import get_auth_state
from ..db.sql.session import SqlSessionDep
from ..dual.protected import roles_router

logger = logging.getLogger(__name__)


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload: dict, *, secret: str) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, sha256).digest()
    return _b64u(body) + "." + _b64u(sig)


def _verify(token: str, *, secret: str) -> dict:
    try:
        b64_body, b64_sig = token.split(".", 1)
        body = _b64u_decode(b64_body)
        exp_sig = _b64u_decode(b64_sig)
        got_sig = hmac.new(secret.encode("utf-8"), body, sha256).digest()
        if not hmac.compare_digest(exp_sig, got_sig):
            raise ValueError("bad_signature")
        payload = json.loads(body)
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception as e:
        raise ValueError("invalid_token") from e


def admin_router(*, dependencies: Optional[list[Any]] = None, **kwargs) -> APIRouter:
    """Role-gated admin router for coarse access control.

    Use permission guards inside endpoints for fine-grained control.
    """

    return roles_router("admin", **kwargs)


def add_admin(
    app,
    *,
    base_path: str = "/admin",
    enable_impersonation: bool = True,
    secret: Optional[str] = None,
    ttl_seconds: int = 15 * 60,
    cookie_name: str = "impersonation",
    impersonation_user_getter: Optional[Callable[[Any, str], Any]] = None,
) -> None:
    """Wire admin surfaces with sensible defaults.

    - Mounts an admin router under base_path.
    - Optionally enables impersonation start/stop endpoints guarded by permissions.
    - Registers a dependency override to honor impersonation cookie globally (idempotent).

    impersonation_user_getter: optional callable (request, user_id) -> user object.
      If omitted, defaults to loading from SQLAlchemy User model returned by get_auth_state().
    """

    # Idempotency: only mount once per app instance
    if getattr(app.state, "_admin_added", False):
        return

    env = get_current_environment()
    _secret = (
        secret or os.getenv("ADMIN_IMPERSONATION_SECRET") or os.getenv("APP_SECRET") or "dev-secret"
    )
    _ttl = int(os.getenv("ADMIN_IMPERSONATION_TTL", str(ttl_seconds)))
    _cookie = os.getenv("ADMIN_IMPERSONATION_COOKIE", cookie_name)

    r = admin_router(prefix=base_path, tags=["admin"])  # role-gated

    async def _default_user_getter(request: Request, user_id: str, session: SqlSessionDep):
        try:
            UserModel, _, _ = get_auth_state()
        except Exception:
            # Fallback: simple shim if auth state not configured
            return SimpleNamespace(id=user_id)
        obj = await session.get(UserModel, user_id)
        if not obj:
            raise HTTPException(404, "user_not_found")
        return obj

    user_getter = impersonation_user_getter

    @r.post(
        "/impersonate/start", status_code=204, dependencies=[RequirePermission("admin.impersonate")]
    )
    async def start_impersonation(
        body: dict, request: Request, response: Response, session: SqlSessionDep, identity: Identity
    ):
        target_id = (body or {}).get("user_id")
        reason = (body or {}).get("reason", "")
        if not target_id:
            raise HTTPException(422, "user_id_required")
        # Load target for validation (custom getter or default)
        _res = (
            user_getter(request, target_id)
            if user_getter
            else _default_user_getter(request, target_id, session)
        )
        target = await _res if inspect.isawaitable(_res) else _res
        actor: Principal = identity
        payload = {
            "actor_id": getattr(getattr(actor, "user", None), "id", None),
            "target_id": str(getattr(target, "id", target_id)),
            "iat": int(time.time()),
            "exp": int(time.time()) + _ttl,
            "nonce": _b64u(os.urandom(8)),
        }
        token = _sign(payload, secret=_secret)
        response.set_cookie(
            key=_cookie,
            value=token,
            httponly=True,
            samesite="lax",
            secure=(env in ("prod", "production")),
            path="/",
            max_age=_ttl,
        )
        logger.info(
            "admin.impersonation.started",
            extra={
                "actor_id": payload["actor_id"],
                "target_id": payload["target_id"],
                "reason": reason,
                "expires_in": _ttl,
            },
        )
        # Re-compose override now to wrap any late overrides set by tests/harness
        try:
            _compose_override()
        except Exception:
            pass

    @r.post("/impersonate/stop", status_code=204)
    async def stop_impersonation(response: Response):
        response.delete_cookie(_cookie, path="/")
        logger.info("admin.impersonation.stopped")

    app.include_router(r)

    # Dependency override: wrap the base principal to honor impersonation cookie.
    # Compose with any existing override (e.g., acceptance app/test harness) and
    # re-compose at startup to capture late overrides.
    def _compose_override():
        existing = app.dependency_overrides.get(_current_principal)
        if existing and getattr(existing, "_is_admin_impersonation_override", False):
            dep_provider = getattr(existing, "_admin_impersonation_base", _current_principal)
        else:
            dep_provider = existing or _current_principal

        async def _override_current_principal(
            base: Principal = Depends(dep_provider),
            request: Request = None,
            session: SqlSessionDep = None,
        ) -> Principal:
            token = request.cookies.get(_cookie) if request else None
            if not token:
                return base
            try:
                payload = _verify(token, secret=_secret)
            except Exception:
                return base
            # Load target user
            target_id = payload.get("target_id")
            if not target_id:
                return base
            # Preserve actor roles/claims so permissions remain that of the actor
            actor_user = getattr(base, "user", None)
            actor_roles = getattr(actor_user, "roles", []) or []
            _res = (
                user_getter(request, target_id)
                if user_getter
                else _default_user_getter(request, target_id, session)
            )
            target = await _res if inspect.isawaitable(_res) else _res
            # Swap user but keep actor for audit if needed
            setattr(base, "actor", getattr(base, "user", None))
            # If target lacks roles, inherit actor roles to maintain permission checks
            try:
                if not getattr(target, "roles", None):
                    setattr(target, "roles", actor_roles)
            except Exception:
                # Best-effort; if target object is immutable, fallback by wrapping
                target = SimpleNamespace(id=getattr(target, "id", target_id), roles=actor_roles)
            base.user = target
            base.via = "impersonated"
            return base

        app.dependency_overrides[_current_principal] = _override_current_principal
        _override_current_principal._is_admin_impersonation_override = True  # type: ignore[attr-defined]
        _override_current_principal._admin_impersonation_base = dep_provider  # type: ignore[attr-defined]

    # Compose now (best-effort) and again on startup to wrap any later overrides
    _compose_override()
    try:
        app.add_event_handler("startup", _compose_override)
    except Exception:
        # Best-effort; if app doesn't support event handlers, we already composed once
        pass
    app.state._admin_added = True


# no extra helpers
