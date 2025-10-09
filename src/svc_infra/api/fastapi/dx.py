"""
Developer Experience (DX) facade: the handful of things app engineers should import.

Usage:
    from svc_infra.dx import (
        # App bootstrap
        easy_service_app, easy_service_api, EasyAppOptions, LoggingOptions, ObservabilityOptions,

        # Auth bootstrap
        add_auth_users, get_auth_settings, AuthSettings, AuthPolicy, DefaultAuthPolicy,

        # Identity (endpoint params + router deps + guards)
        Principal, Identity, OptionalIdentity,
        RequireIdentity, AllowIdentity,
        RequireUser, RequireService, RequireScopes, RequireAnyScope,

        # Routers (pre-wired security + OpenAPI)
        public_router, optional_identity_router, protected_router, user_router, service_router, scopes_router,

        # Turnkey auth feature routers (optional)
        apikey_router, mfa_router, account_router, oauth_router_with_backend,

        # API Key model binding (only if enabling API keys)
        bind_apikey_model, get_apikey_model,

        # Docs (only if you run a raw FastAPI app yourself)
        install_openapi_auth,
    )
"""

# ----------------
# Auth bootstrap / config
# ----------------
from svc_infra.api.fastapi.auth.add import add_auth_users
from svc_infra.api.fastapi.auth.mfa.router import mfa_router
from svc_infra.api.fastapi.auth.mfa.security import RequireMFAIfEnabled
from svc_infra.api.fastapi.auth.policy import AuthPolicy, DefaultAuthPolicy
from svc_infra.api.fastapi.auth.routers.account import account_router

# ----------------
# Turnkey feature routers (opt-in)
# ----------------
from svc_infra.api.fastapi.auth.routers.apikey_router import apikey_router
from svc_infra.api.fastapi.auth.routers.oauth_router import oauth_router_with_backend

# ----------------
# Identity primitives (endpoint params + router-level deps + guard factories)
# ----------------
from svc_infra.api.fastapi.auth.security import (
    AllowIdentity,
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
from svc_infra.api.fastapi.auth.settings import AuthSettings, get_auth_settings
from svc_infra.api.fastapi.dual.protected import (
    optional_identity_router,
    protected_router,
    roles_router,
    scopes_router,
    service_router,
    user_router,
)

# ----------------
# Pre-wired routers (OpenAPI security auto-injected)
# ----------------
from svc_infra.api.fastapi.dual.public import public_router

# ----------------
# App bootstrap
# ----------------
from svc_infra.api.fastapi.ease import (
    EasyAppOptions,
    LoggingOptions,
    ObservabilityOptions,
    easy_service_api,
    easy_service_app,
)

# ----------------
# OpenAPI auth schemes installer (only when building a bare FastAPI app yourself)
# ----------------
from svc_infra.api.fastapi.openapi.security import install_openapi_auth

# ----------------
# API key model binding (needed before using apikey_router if enable_api_keys=True)
# ----------------
from svc_infra.db.sql.apikey import bind_apikey_model, get_apikey_model

__all__ = [
    # App bootstrap
    "easy_service_app",
    "easy_service_api",
    "EasyAppOptions",
    "LoggingOptions",
    "ObservabilityOptions",
    # Auth bootstrap / config
    "add_auth_users",
    "get_auth_settings",
    "AuthSettings",
    "AuthPolicy",
    "DefaultAuthPolicy",
    # Identity
    "Principal",
    "Identity",
    "OptionalIdentity",
    "RequireIdentity",
    "AllowIdentity",
    "RequireUser",
    "RequireService",
    "RequireScopes",
    "RequireAnyScope",
    "RequireRoles",
    "RequireMFAIfEnabled",
    # Routers
    "public_router",
    "optional_identity_router",
    "protected_router",
    "user_router",
    "service_router",
    "scopes_router",
    "roles_router",
    # Feature routers
    "apikey_router",
    "mfa_router",
    "account_router",
    "oauth_router_with_backend",
    # API key model
    "bind_apikey_model",
    "get_apikey_model",
    # Docs wiring
    "install_openapi_auth",
]
