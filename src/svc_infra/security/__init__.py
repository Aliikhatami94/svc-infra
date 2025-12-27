"""Security module providing authentication, authorization, and protection utilities.

This module provides comprehensive security primitives:

- **Middleware**: Security headers (CSP, HSTS, etc.) and CORS configuration
- **Lockout**: Account lockout with exponential backoff for brute force protection
- **Passwords**: Password policy validation with HIBP breach checking
- **Sessions**: Session and refresh token management
- **Audit**: Hash-chain audit logging for tamper detection
- **JWT Rotation**: Seamless JWT key rotation support
- **Permissions**: RBAC and ABAC authorization helpers
- **Signed Cookies**: Cryptographically signed cookies with expiry

Example:
    from fastapi import FastAPI
    from svc_infra.security import add_security

    app = FastAPI()

    # Add security headers and CORS
    add_security(app, cors_origins=["https://myapp.com"])

    # Use password validation
    from svc_infra.security import validate_password, PasswordPolicy

    policy = PasswordPolicy(min_length=12, require_symbol=True)
    validate_password("MyStr0ng!Pass", policy)

    # Use lockout protection
    from svc_infra.security import get_lockout_status, LockoutConfig

    status = await get_lockout_status(session, user_id=user.id, ip_hash=ip_hash)
    if status.locked:
        raise HTTPException(429, "Too many attempts")

Environment Variables:
    CORS_ALLOW_ORIGINS: Comma-separated list of allowed origins
    CORS_ALLOW_CREDENTIALS: Allow credentials in CORS (true/false)
    CORS_ALLOW_METHODS: Comma-separated list of allowed methods
    CORS_ALLOW_HEADERS: Comma-separated list of allowed headers

See Also:
    - docs/security.md for detailed documentation
    - svc_infra.api.fastapi.auth for authentication routes
"""

from __future__ import annotations

# FastAPI integration
from .add import add_security

# Audit logging
from .audit import (
    AuditEvent,
    AuditLogStore,
    InMemoryAuditLogStore,
    append_audit_event,
    verify_audit_chain,
)
from .audit_service import append_event, verify_chain_for_tenant

# Security headers middleware
from .headers import SECURE_DEFAULTS, SecurityHeadersMiddleware

# HIBP breach checking
from .hibp import HIBPClient

# JWT rotation
from .jwt_rotation import RotatingJWTStrategy

# Account lockout
from .lockout import (
    LockoutConfig,
    LockoutStatus,
    compute_lockout,
    get_lockout_status,
    record_attempt,
)

# Models (for type hints and direct use)
from .models import (
    AuditLog,
    AuthSession,
    FailedAuthAttempt,
    RefreshToken,
    RefreshTokenRevocation,
    compute_audit_hash,
)

# Password validation
from .passwords import (
    PasswordPolicy,
    PasswordValidationError,
    configure_breached_checker,
    validate_password,
)

# RBAC/ABAC permissions
from .permissions import (
    PERMISSION_REGISTRY,
    RequireABAC,
    RequireAnyPermission,
    RequirePermission,
    enforce_abac,
    extend_role,
    get_permissions_for_roles,
    has_permission,
    owns_resource,
    principal_permissions,
    register_role,
)

# Signed cookies
from .signed_cookies import sign_cookie, verify_cookie

__all__ = [
    # FastAPI integration
    "add_security",
    # Headers middleware
    "SecurityHeadersMiddleware",
    "SECURE_DEFAULTS",
    # Lockout
    "LockoutConfig",
    "LockoutStatus",
    "compute_lockout",
    "record_attempt",
    "get_lockout_status",
    # Password validation
    "PasswordPolicy",
    "PasswordValidationError",
    "validate_password",
    "configure_breached_checker",
    # HIBP
    "HIBPClient",
    # Signed cookies
    "sign_cookie",
    "verify_cookie",
    # Audit logging
    "AuditLogStore",
    "AuditEvent",
    "append_audit_event",
    "verify_audit_chain",
    "append_event",
    "verify_chain_for_tenant",
    "InMemoryAuditLogStore",
    # JWT rotation
    "RotatingJWTStrategy",
    # Permissions (RBAC/ABAC)
    "PERMISSION_REGISTRY",
    "register_role",
    "extend_role",
    "get_permissions_for_roles",
    "principal_permissions",
    "has_permission",
    "RequirePermission",
    "RequireAnyPermission",
    "RequireABAC",
    "enforce_abac",
    "owns_resource",
    # Models
    "AuthSession",
    "RefreshToken",
    "RefreshTokenRevocation",
    "FailedAuthAttempt",
    "AuditLog",
    "compute_audit_hash",
]
