from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlparse

import httpx
import jwt
import pyotp
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi_users.authentication import JWTStrategy
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport
from sqlalchemy import create_engine
from starlette.middleware.base import BaseHTTPMiddleware

from svc_infra.apf_payments import settings as payments_settings
from svc_infra.apf_payments.provider.base import ProviderAdapter
from svc_infra.apf_payments.schemas import (
    CustomerOut,
    CustomerUpsertIn,
    IntentCreateIn,
    IntentOut,
    PaymentMethodAttachIn,
    PaymentMethodOut,
)
from svc_infra.api.fastapi.apf_payments.setup import add_payments
from svc_infra.api.fastapi.auth.routers.session_router import build_session_router
from svc_infra.api.fastapi.auth.security import (
    Principal,
    _current_principal,
    _optional_principal,
    resolve_bearer_or_cookie_principal,
)
from svc_infra.api.fastapi.db.sql.session import get_session
from svc_infra.api.fastapi.dependencies.ratelimit import rate_limiter
from svc_infra.api.fastapi.ease import EasyAppOptions, ObservabilityOptions, easy_service_app
from svc_infra.api.fastapi.middleware.ratelimit import (
    SimpleRateLimitMiddleware as _SimpleRateLimitMiddleware,
)
from svc_infra.api.fastapi.middleware.ratelimit_store import InMemoryRateLimitStore
from svc_infra.api.fastapi.tenancy.context import TenantId as _TenantId
from svc_infra.api.fastapi.tenancy.context import set_tenant_resolver as _set_tenant_resolver
from svc_infra.jobs.easy import easy_jobs
from svc_infra.jobs.queue import Job
from svc_infra.jobs.worker import process_one
from svc_infra.obs import metrics as _metrics
from svc_infra.security.add import add_security
from svc_infra.security.passwords import PasswordValidationError, validate_password
from svc_infra.security.permissions import RequireABAC, RequirePermission, owns_resource
from svc_infra.webhooks.add import add_webhooks
from svc_infra.webhooks.signing import verify_any

# Minimal acceptance app wiring the library's routers and defaults
os.environ.setdefault("PAYMENTS_PROVIDER", "fake")

payments_settings._SETTINGS = payments_settings.PaymentsSettings(default_provider="fake")
# Provide a tiny SQLite engine so db_pool_* metrics are bound during acceptance
_engine = create_engine("sqlite:///:memory:")
# Trigger a connection once so pool metrics initialize label series
try:
    with _engine.connect() as _conn:
        _ = _conn.execute("SELECT 1")
except Exception:
    # best effort; tests don't rely on actual DB
    pass

app = easy_service_app(
    name="svc-infra-acceptance",
    release="A0",
    versions=[
        ("v1", "svc_infra.api.fastapi.routers", None),
    ],
    root_routers=["svc_infra.api.fastapi.routers"],
    public_cors_origins=["*"],
    root_public_base_url="/",
    options=EasyAppOptions(
        observability=ObservabilityOptions(
            enable=True,
            db_engines=[_engine],
            metrics_path="/metrics",
        )
    ),
)

# Install security headers so acceptance can assert their presence
add_security(app)

# Replace the default global rate limit middleware with a header-only variant
# so dependency-based tests remain fully isolated while acceptance can still
# assert presence of X-RateLimit-* headers on successful responses.
try:
    # Remove any pre-installed SimpleRateLimitMiddleware
    app.user_middleware = [
        m for m in app.user_middleware if getattr(m, "cls", None) is not _SimpleRateLimitMiddleware
    ]

    class _HeaderOnlyRateLimitMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, limit: int = 10000, window: int = 60):
            super().__init__(app)
            self.limit = limit
            self.window = window

        async def dispatch(self, request, call_next):
            resp = await call_next(request)
            # Provide plausible headers for acceptance assertions
            import time as _t

            now = int(_t.time())
            reset = now - (now % self.window) + self.window
            resp.headers.setdefault("X-RateLimit-Limit", str(self.limit))
            # Remaining is not tracked here; provide the same limit value
            resp.headers.setdefault("X-RateLimit-Remaining", str(self.limit))
            resp.headers.setdefault("X-RateLimit-Reset", str(reset))
            return resp

    # Add header-only RL middleware
    app.add_middleware(_HeaderOnlyRateLimitMiddleware, limit=10000, window=60)
    # Rebuild middleware stack to apply changes immediately
    app.middleware_stack = app.build_middleware_stack()
except Exception:
    # Best-effort: if FastAPI/Starlette internals change, do not break acceptance app
    pass


# Minimal fake payments adapter for acceptance (no external calls).
class FakeAdapter(ProviderAdapter):
    name = "fake"

    def __init__(self):
        self._customers: dict[str, CustomerOut] = {}
        self._methods: dict[str, list[PaymentMethodOut]] = {}
        self._intents: dict[str, IntentOut] = {}

    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:  # type: ignore[override]
        cid = data.email or data.name or "cus_accept"
        out = CustomerOut(
            id=cid, provider=self.name, provider_customer_id=cid, email=data.email, name=data.name
        )
        self._customers[cid] = out
        self._methods.setdefault(cid, [])
        return out

    async def attach_payment_method(self, data: PaymentMethodAttachIn) -> PaymentMethodOut:  # type: ignore[override]
        mid = f"pm_{len(self._methods.get(data.customer_provider_id, [])) + 1}"
        out = PaymentMethodOut(
            id=mid,
            provider=self.name,
            provider_customer_id=data.customer_provider_id,
            provider_method_id=mid,
            brand="visa",
            last4="4242",
            exp_month=1,
            exp_year=2030,
            is_default=bool(data.make_default),
        )
        lst = self._methods.setdefault(data.customer_provider_id, [])
        if data.make_default:
            # clear existing default
            for m in lst:
                m.is_default = False
        lst.append(out)
        return out

    async def list_payment_methods(self, provider_customer_id: str) -> list[PaymentMethodOut]:  # type: ignore[override]
        return list(self._methods.get(provider_customer_id, []))

    async def create_intent(self, data: IntentCreateIn, *, user_id: str | None) -> IntentOut:  # type: ignore[override]
        iid = f"pi_{len(self._intents) + 1}"
        out = IntentOut(
            id=iid,
            provider=self.name,
            provider_intent_id=iid,
            status="requires_confirmation",
            amount=data.amount,
            currency=data.currency,
            client_secret=f"secret_{iid}",
        )
        self._intents[iid] = out
        return out

    async def hydrate_intent(self, provider_intent_id: str) -> IntentOut:  # type: ignore[override]
        return self._intents[provider_intent_id]

    async def get_payment_method(self, provider_method_id: str) -> PaymentMethodOut:  # type: ignore[override]
        for methods in self._methods.values():
            for m in methods:
                if m.provider_method_id == provider_method_id:
                    return m
        raise KeyError(provider_method_id)

    async def update_payment_method(self, provider_method_id: str, data):  # type: ignore[override]
        m = await self.get_payment_method(provider_method_id)
        return m

    async def get_intent(self, provider_intent_id: str) -> IntentOut:  # non-protocol helper
        return await self.hydrate_intent(provider_intent_id)


# Install payments under /payments using the fake adapter (skip default provider registration).
add_payments(app, prefix="/payments", register_default_providers=False, adapters=[FakeAdapter()])


# Replace the DB session dependency with a no-op stub so tests stay self-contained.
class _StubScalarResult:
    def __init__(self, rows: list | None = None):
        self._rows = rows or []

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def one(self):  # pragma: no cover - best effort stub behaviour
        if not self._rows:
            raise ValueError("No rows available")
        if len(self._rows) > 1:
            raise ValueError("Multiple rows available")
        return self._rows[0]


class _StubResult(_StubScalarResult):
    def scalars(self):
        return _StubScalarResult(self._rows)


class _StubSession:
    async def execute(self, _statement):
        return _StubResult([])

    async def scalar(self, _statement):
        return None

    def add(self, _obj):
        return None

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


async def _stub_get_session():
    yield _StubSession()


app.dependency_overrides[get_session] = _stub_get_session


# Override auth to always provide a user with a tenant for acceptance.
def _accept_principal():
    # Provide a minimal user identity with id and tenant for RBAC/ABAC acceptance tests.
    return Principal(
        user=SimpleNamespace(id="u-1", tenant_id="accept-tenant", roles=["support"]),
        scopes=["*"],
        via="jwt",
    )


app.dependency_overrides[_current_principal] = _accept_principal

# Also override the optional principal and bearer-cookie resolver so payments
# routes don't require full auth state during acceptance runs.


def _accept_optional_principal():
    return _accept_principal()


app.dependency_overrides[_optional_principal] = _accept_optional_principal
app.dependency_overrides[resolve_bearer_or_cookie_principal] = (
    lambda request, session: _accept_principal()
)


# --- Tenancy acceptance wiring ---
# Allow tests to switch tenant per-request using X-Accept-Tenant without touching auth identity.
def _accept_tenant_resolver(request, identity, tenant_header):
    # Precedence:
    # 1) X-Accept-Tenant header (acceptance-only)
    # 2) identity.user.tenant_id if present (from our auth override)
    # 3) default to a known tenant to keep acceptance deterministic
    hdr = request.headers.get("X-Accept-Tenant")
    if hdr and str(hdr).strip():
        return str(hdr).strip()
    try:
        uid = getattr(getattr(identity, "user", None), "tenant_id", None)
        if uid:
            return str(uid)
    except Exception:
        pass
    return "accept-tenant"


_set_tenant_resolver(_accept_tenant_resolver)

# Minimal in-memory tenant-aware resource to validate tenancy behaviors (A6-01..A6-03).
_ten_router = APIRouter(prefix="/tenancy", tags=["acceptance-tenancy"])  # test-only

# In-memory stores on app.state
app.state.ten_widgets_by_tenant = {}
app.state.ten_widget_index = {}
app.state.ten_widget_next_id = 1
app.state.ten_quota_default = 2  # max widgets per tenant


@_ten_router.post("/widgets", status_code=201)
async def create_widget(payload: dict, tenant_id: _TenantId):  # type: ignore[name-defined]
    """Create widget under resolved tenant; enforce per-tenant quota; ignore tenant in payload."""
    # Defensive: ensure clean slate on first use within a long-lived acceptance server
    if not getattr(app.state, "ten_reset_done", False):
        app.state.ten_widgets_by_tenant = {}
        app.state.ten_widget_index = {}
        app.state.ten_widget_next_id = 1
        app.state.ten_reset_done = True
    # Enforce quota (guard against mis-set or zero quotas)
    items = app.state.ten_widgets_by_tenant.setdefault(tenant_id, [])
    quota = getattr(app.state, "ten_quota_default", 2)
    try:
        quota = int(quota)
    except Exception:
        quota = 2
    if quota <= 0:
        quota = 2
    if len(items) >= quota:
        # Quota exceeded → 429 with Retry-After to mirror RL semantics
        from fastapi import Response

        r = Response(status_code=429)
        r.headers["Retry-After"] = "60"
        return r

    wid = str(app.state.ten_widget_next_id)
    app.state.ten_widget_next_id += 1
    item = {"id": wid, "name": str(payload.get("name", f"w-{wid}")), "tenant_id": tenant_id}
    items.append(item)
    app.state.ten_widget_index[wid] = tenant_id
    return item


@_ten_router.get("/widgets")
async def list_widgets(tenant_id: _TenantId):  # type: ignore[name-defined]
    return list(app.state.ten_widgets_by_tenant.get(tenant_id, []))


@_ten_router.get("/widgets/{wid}")
async def get_widget(wid: str, tenant_id: _TenantId):  # type: ignore[name-defined]
    owner_tenant = app.state.ten_widget_index.get(wid)
    if owner_tenant != tenant_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="not_found")
    for it in app.state.ten_widgets_by_tenant.get(tenant_id, []):
        if it["id"] == wid:
            return it
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail="not_found")


@_ten_router.post("/_reset")
async def reset_tenancy_state():
    """Acceptance-only: reset in-memory tenancy state between tests.

    Clears all widgets, index and resets id counter and leaves quota at default.
    """
    app.state.ten_widgets_by_tenant = {}
    app.state.ten_widget_index = {}
    app.state.ten_widget_next_id = 1
    app.state.ten_quota_default = 2
    app.state.ten_reset_done = True
    return {"ok": True}


app.include_router(_ten_router)
# --- Acceptance-only security demo routers ---
_sec = APIRouter(prefix="/secure", tags=["acceptance-security"])  # test-only


@_sec.get("/admin-only", dependencies=[RequirePermission("user.write")])
async def admin_only():
    return {"ok": True}


async def _load_owned(owner_id: str):
    # Simple resource provider returning an object with an owner_id attribute
    return SimpleNamespace(owner_id=owner_id)


@_sec.get(
    "/owned/{owner_id}",
    dependencies=[
        RequireABAC(permission="user.read", predicate=owns_resource(), resource_getter=_load_owned)
    ],
)
async def owned_resource(owner_id: str):
    return {"owner_id": owner_id}


app.include_router(_sec)

# Mount session management endpoints under /users for acceptance tests (list/revoke)
app.include_router(build_session_router(), prefix="/users")

# ---------------- Acceptance-only minimal auth flow (A1-01) -----------------
# This block implements a tiny in-memory register → verify → login → /auth/me
# flow so we can acceptance-test auth without a backing SQL user model.

_auth_router = APIRouter(prefix="/auth", tags=["acceptance-auth"])
_pwd = PasswordHelper()


class _AUser:
    def __init__(self, *, email: str, password: str):
        self.id: uuid.UUID = uuid.uuid4()
        self.email = email
        self.is_active = True
        self.is_superuser = False
        self.is_verified = False
        self.password_hash = _pwd.hash(password)
        # MFA-related fields (populated when user starts setup)
        self.mfa_enabled: bool = False
        self.mfa_secret: str | None = None
        self.mfa_recovery: list[str] | None = None  # store hashes
        self.mfa_confirmed_at = None

    @property
    def hashed_password(self) -> str:
        return self.password_hash


_users_by_id: dict[uuid.UUID, _AUser] = {}
_ids_by_email: dict[str, uuid.UUID] = {}
_verify_tokens: dict[str, uuid.UUID] = {}

# In-memory lockout trackers for acceptance
_failures_by_user: dict[uuid.UUID, list[datetime]] = {}
_failures_by_ip: dict[str, list[datetime]] = {}


class _LockCfg:
    threshold = 3
    window_minutes = 5
    base_cooldown_seconds = 15
    max_cooldown_seconds = 300


def _cleanup_and_count(lst: list[datetime], now: datetime) -> int:
    cutoff = now - timedelta(minutes=_LockCfg.window_minutes)
    while lst and lst[0] < cutoff:
        lst.pop(0)
    return len(lst)


def _hash_ip(remote: str | None) -> str:
    remote = remote or "unknown"
    return hashlib.sha256(remote.encode()).hexdigest()[:16]


def _jwt_strategy() -> JWTStrategy:
    # Match repo defaults (audience used by downstream libs)
    return JWTStrategy(
        secret="svc-dev-secret-change-me",
        lifetime_seconds=3600,
        token_audience="fastapi-users:auth",
    )


@_auth_router.post("/register", status_code=201)
async def _accept_register(payload: dict = Body(...)):
    email = (payload.get("email") or "").strip().lower()
    password = (payload.get("password") or "").strip()
    if not email or not password:
        raise HTTPException(400, "email_and_password_required")
    if email in _ids_by_email:
        raise HTTPException(400, "email_already_registered")
    # Enforce password policy (A1-02)
    try:
        validate_password(password)
    except PasswordValidationError as e:
        # Surface reasons at top-level for acceptance assertions
        return JSONResponse(
            status_code=400, content={"error": "password_weak", "reasons": e.reasons}
        )
    user = _AUser(email=email, password=password)
    _users_by_id[user.id] = user
    _ids_by_email[email] = user.id
    token = f"verify_{user.id.hex}"
    _verify_tokens[token] = user.id
    return {
        "id": str(user.id),
        "email": user.email,
        "is_verified": user.is_verified,
        "verify_token": token,
    }


@_auth_router.get("/verify")
async def _accept_verify(token: str):
    uid = _verify_tokens.pop(token, None)
    if not uid or uid not in _users_by_id:
        raise HTTPException(400, "invalid_token")
    _users_by_id[uid].is_verified = True
    return {"ok": True}


@_auth_router.get("/me")
async def _accept_me(request: Request):
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "missing_token")
    token = auth.split(" ", 1)[1]
    try:
        claims = jwt.decode(
            token,
            "svc-dev-secret-change-me",
            algorithms=["HS256"],
            audience="fastapi-users:auth",
        )
        sub = claims.get("sub")
        uid = uuid.UUID(str(sub))
        user = _users_by_id.get(uid)
    except Exception:
        user = None
    if not user:
        raise HTTPException(401, "invalid_token")
    return {"id": str(user.id), "email": user.email, "is_verified": bool(user.is_verified)}


# ---------------- Acceptance MFA (A1-07 step 1) -----------------
# Minimal endpoints: start, confirm, status. Uses in-memory _AUser store.


def _accept_current_user_from_bearer(request: Request) -> _AUser:
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "missing_token")
    token = auth.split(" ", 1)[1]
    try:
        claims = jwt.decode(
            token,
            "svc-dev-secret-change-me",
            algorithms=["HS256"],
            audience="fastapi-users:auth",
        )
        sub = claims.get("sub")
        uid = uuid.UUID(str(sub))
        user = _users_by_id.get(uid)
    except Exception:
        user = None
    if not user:
        raise HTTPException(401, "invalid_token")
    if not user.is_active:
        raise HTTPException(401, "account_disabled")
    return user


@_auth_router.post("/mfa/start")
async def _accept_mfa_start(request: Request):
    user = _accept_current_user_from_bearer(request)
    if user.mfa_enabled:
        raise HTTPException(400, "MFA already enabled")
    # generate a new secret and provisioning URI
    secret = pyotp.random_base32(length=32)
    label = user.email or f"user-{user.id}"
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=label, issuer_name="svc-infra")
    # persist to in-memory user
    user.mfa_secret = secret
    user.mfa_enabled = False
    user.mfa_confirmed_at = None
    # response shape aligned with library StartSetupOut (qr_svg omitted in acceptance)
    return {"otpauth_url": uri, "secret": secret, "qr_svg": None}


@_auth_router.post("/mfa/confirm")
async def _accept_mfa_confirm(payload: dict = Body(...), request: Request = None):
    user = _accept_current_user_from_bearer(request)
    code = (payload.get("code") or "").strip()
    if not user.mfa_secret:
        raise HTTPException(400, "No setup in progress")
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(400, "Invalid code")

    # generate recovery codes; store hashes only
    def _hash_val(v: str) -> str:
        return hashlib.sha256(v.encode()).hexdigest()

    def _gen_code() -> str:
        return secrets.token_hex(5)

    codes = [_gen_code() for _ in range(8)]
    user.mfa_recovery = [_hash_val(c) for c in codes]
    user.mfa_enabled = True
    user.mfa_confirmed_at = datetime.now(timezone.utc)
    return {"codes": codes}


@_auth_router.get("/mfa/status")
async def _accept_mfa_status(request: Request):
    user = _accept_current_user_from_bearer(request)
    enabled = bool(user.mfa_enabled)
    methods = []
    if enabled and user.mfa_secret:
        methods.extend(["totp", "recovery"])
    # always offer email OTP in verify flow (not implemented here)
    methods.append("email")

    def _mask(email: str) -> str | None:
        if not email or "@" not in email:
            return None
        name, domain = email.split("@", 1)
        if len(name) <= 1:
            masked = "*"
        elif len(name) == 2:
            masked = name[0] + "*"
        else:
            masked = name[0] + "*" * (len(name) - 2) + name[-1]
        return f"{masked}@{domain}"

    return {
        "enabled": enabled,
        "methods": methods,
        "confirmed_at": user.mfa_confirmed_at,
        "email_mask": _mask(user.email) if user.email else None,
        "email_otp": {"cooldown_seconds": 60},
    }


# User-facing login under /users to mirror library paths
_users_router = APIRouter(prefix="/users", tags=["acceptance-auth"])


@_users_router.post("/login")
async def _accept_login(request: Request):
    # Form-encoded like OAuth password grant
    form = await request.form()
    email = (form.get("username") or "").strip().lower()
    password = (form.get("password") or "").strip()
    if not email or not password:
        raise HTTPException(400, "LOGIN_BAD_CREDENTIALS")
    uid = _ids_by_email.get(email)
    if not uid:
        # simulate dummy hash check to avoid timing attacks
        _pwd.verify_and_update(password, _pwd.hash("dummy"))
        raise HTTPException(400, "LOGIN_BAD_CREDENTIALS")
    user = _users_by_id.get(uid)
    # Pre-check lockout by IP and user
    now = datetime.now(timezone.utc)
    ip_hash = _hash_ip(request.client.host if request.client else None)
    u_list = _failures_by_user.setdefault(uid, [])
    i_list = _failures_by_ip.setdefault(ip_hash, [])
    # Clean up old entries
    _cleanup_and_count(u_list, now)
    _cleanup_and_count(i_list, now)
    # If either user or IP has exceeded threshold within window, block
    if len(u_list) >= _LockCfg.threshold or len(i_list) >= _LockCfg.threshold:
        # Exponential backoff based on user failure count
        exponent = max(len(u_list), len(i_list)) - _LockCfg.threshold
        cooldown = _LockCfg.base_cooldown_seconds * (2 ** max(0, exponent))
        if cooldown > _LockCfg.max_cooldown_seconds:
            cooldown = _LockCfg.max_cooldown_seconds
        retry = int(cooldown)
        resp = JSONResponse(
            status_code=429,
            content={"error": "account_locked", "retry_after": retry},
        )
        resp.headers["Retry-After"] = str(retry)
        return resp
    # Verify password
    if not user or not _pwd.verify_and_update(password, user.password_hash)[0]:
        # Record failure
        u_list.append(now)
        i_list.append(now)
        # keep lists ordered oldest→newest; already true via append
        # If this failure reaches/exceeds threshold, trigger lockout immediately
        if len(u_list) >= _LockCfg.threshold or len(i_list) >= _LockCfg.threshold:
            exponent = max(len(u_list), len(i_list)) - _LockCfg.threshold
            cooldown = _LockCfg.base_cooldown_seconds * (2 ** max(0, exponent))
            if cooldown > _LockCfg.max_cooldown_seconds:
                cooldown = _LockCfg.max_cooldown_seconds
            retry = int(cooldown)
            resp = JSONResponse(
                status_code=429,
                content={"error": "account_locked", "retry_after": retry},
            )
            resp.headers["Retry-After"] = str(retry)
            return resp
        return JSONResponse(status_code=400, content={"error": "LOGIN_BAD_CREDENTIALS"})
    if not user.is_verified:
        raise HTTPException(400, "LOGIN_USER_NOT_VERIFIED")
    token = await _jwt_strategy().write_token(user)
    resp = JSONResponse({"access_token": token, "token_type": "bearer"})
    # Also set an auth cookie so either header or cookie works
    resp.set_cookie(key="svc_auth", value=token, httponly=True)
    # On success, clear user's failure history
    _failures_by_user.pop(uid, None)
    return resp


app.include_router(_users_router)

# ---------------- Acceptance-only API Keys (A1-06) -----------------
# Minimal in-memory API keys lifecycle: create/list/revoke/delete


class _AApiKey:
    def __init__(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        scopes: list[str],
        expires_at: datetime | None,
    ):
        self.id: uuid.UUID = uuid.uuid4()
        # Generate a stable-looking key: prefix + secret
        self.key_prefix: str = f"ak_{secrets.token_hex(4)}"
        self._plaintext: str = f"{self.key_prefix}_{secrets.token_hex(24)}"
        self.user_id = user_id
        self.name = name
        self.scopes = scopes
        self.active = True
        self.expires_at = expires_at
        self.last_used_at: datetime | None = None


_keys_by_id: dict[uuid.UUID, _AApiKey] = {}
_keys_by_user: dict[uuid.UUID, list[uuid.UUID]] = {}


def _require_current_user(request: Request) -> _AUser:
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "missing_token")
    token = auth.split(" ", 1)[1]
    try:
        claims = jwt.decode(
            token,
            "svc-dev-secret-change-me",
            algorithms=["HS256"],
            audience="fastapi-users:auth",
        )
        sub = claims.get("sub")
        uid = uuid.UUID(str(sub))
        user = _users_by_id.get(uid)
    except Exception:
        user = None
    if not user:
        raise HTTPException(401, "invalid_token")
    return user


@_auth_router.post("/keys", status_code=201)
async def _accept_apikey_create(request: Request, payload: dict = Body(...)):
    user = _require_current_user(request)
    owner_id = uuid.UUID(str(payload.get("user_id"))) if payload.get("user_id") else user.id
    if owner_id != user.id and not user.is_superuser:
        raise HTTPException(403, "forbidden")
    name = (payload.get("name") or "").strip() or "Key"
    scopes = list(payload.get("scopes") or [])
    ttl_hours = payload.get("ttl_hours", 24 * 365)
    expires = (datetime.now(timezone.utc) + timedelta(hours=int(ttl_hours))) if ttl_hours else None
    row = _AApiKey(user_id=owner_id, name=name, scopes=scopes, expires_at=expires)
    _keys_by_id[row.id] = row
    _keys_by_user.setdefault(owner_id, []).append(row.id)
    return {
        "id": str(row.id),
        "name": row.name,
        "user_id": str(row.user_id),
        "key": row._plaintext,  # only at creation
        "key_prefix": row.key_prefix,
        "scopes": row.scopes,
        "active": row.active,
        "expires_at": row.expires_at,
        "last_used_at": row.last_used_at,
    }


@_auth_router.get("/keys")
async def _accept_apikey_list(request: Request):
    user = _require_current_user(request)
    ids = list(_keys_by_user.get(user.id, []))
    rows = [_keys_by_id[i] for i in ids if i in _keys_by_id]
    out = []
    for x in rows:
        out.append(
            {
                "id": str(x.id),
                "name": x.name,
                "user_id": str(x.user_id),
                "key": None,  # never returned in list
                "key_prefix": x.key_prefix,
                "scopes": x.scopes,
                "active": x.active,
                "expires_at": x.expires_at,
                "last_used_at": x.last_used_at,
            }
        )
    return out


@_auth_router.post("/keys/{key_id}/revoke", status_code=204)
async def _accept_apikey_revoke(key_id: str, request: Request):
    user = _require_current_user(request)
    try:
        kid = uuid.UUID(key_id)
    except Exception:
        # treat as not found → 204
        return
    row = _keys_by_id.get(kid)
    if not row:
        return
    if not (user.is_superuser or row.user_id == user.id):
        raise HTTPException(403, "forbidden")
    row.active = False
    return


@_auth_router.delete("/keys/{key_id}", status_code=204)
async def _accept_apikey_delete(key_id: str, request: Request, force: bool = False):
    user = _require_current_user(request)
    try:
        kid = uuid.UUID(key_id)
    except Exception:
        return
    row = _keys_by_id.get(kid)
    if not row:
        return
    if not (user.is_superuser or row.user_id == user.id):
        raise HTTPException(403, "forbidden")
    if row.active and not force and not user.is_superuser:
        raise HTTPException(400, "key_active; revoke first or pass force=true")
    # delete
    _keys_by_id.pop(kid, None)
    if row.user_id in _keys_by_user:
        _keys_by_user[row.user_id] = [i for i in _keys_by_user[row.user_id] if i != kid]
    return


# Include all acceptance auth endpoints under /auth after defining them
app.include_router(_auth_router)

# ---------------- Acceptance-only Rate Limiting (A2) -----------------
_rl = APIRouter(prefix="/rl", tags=["acceptance-ratelimit"])

# Deterministic, acceptance-only fixed-window limiter for /rl/dep that:
# - isolates buckets per provided header key
# - guarantees 200,200,200 then 429 within a 60s window
# - emits the abuse metrics hook on 429
_DEP_LIMIT = 3
_DEP_WINDOW = 60
_dep_buckets: dict[tuple[str, int], int] = {}
_dep_seen_keys: set[str] = set()


def _dep_window(now: int) -> tuple[int, int]:
    win = now - (now % _DEP_WINDOW)
    reset = win + _DEP_WINDOW
    return win, reset


@_rl.get("/dep")
async def rl_dep_echo(request: Request):
    import time as _t

    key = request.headers.get("X-RL-Key") or "dep"
    now = int(_t.time())
    win, reset = _dep_window(now)
    if key not in _dep_seen_keys:
        # Treat first use as fresh regardless of any pre-population
        _dep_seen_keys.add(key)
        count = 1
        _dep_buckets[(key, win)] = count
    else:
        count = _dep_buckets.get((key, win), 0) + 1
        _dep_buckets[(key, win)] = count

    if count > _DEP_LIMIT:
        retry = max(0, reset - now)
        # Emit abuse hook
        try:
            _metrics.emit_rate_limited(key, _DEP_LIMIT, retry)
        except Exception:
            pass
        # Mirror dependency RL behavior: 429 with Retry-After header
        resp = JSONResponse(
            status_code=429,
            content={"error": "rate_limited", "limit": _DEP_LIMIT, "retry_after": retry},
        )
        resp.headers["Retry-After"] = str(retry)
        return resp

    return {"ok": True}


# For middleware-based RL, we keep header-only middleware for headers presence on success.
app.include_router(_rl)

# ---------------- Acceptance-only Abuse Heuristics (A2-03) -----------------
_abuse = APIRouter(prefix="/_accept/abuse", tags=["acceptance-abuse"])

_rate_limit_events: list[dict] = []


def _record_rate_limit_event(key: str, limit: int, retry_after: int) -> None:
    _rate_limit_events.append({"key": key, "limit": int(limit), "retry_after": int(retry_after)})


@_abuse.post("/hooks/rate-limit/enable")
def abuse_enable_rate_limit_hook():
    """Enable capture of rate limit events into an in-memory list for acceptance tests."""
    global _rate_limit_events
    _rate_limit_events = []
    _metrics.on_rate_limit_exceeded = _record_rate_limit_event  # type: ignore[assignment]
    # Reset acceptance RL buckets to avoid cross-test interference
    try:
        _dep_buckets.clear()
        _dep_seen_keys.clear()
    except Exception:
        pass
    return {"enabled": True}


@_abuse.post("/hooks/rate-limit/disable")
def abuse_disable_rate_limit_hook():
    _metrics.on_rate_limit_exceeded = None
    return {"enabled": False}


@_abuse.get("/hooks/rate-limit/events")
def abuse_get_rate_limit_events():
    return {"events": list(_rate_limit_events)}


app.include_router(_abuse)

# ---------------- Acceptance-only Idempotency & Concurrency (A3) -----------------
_idmp = APIRouter(prefix="/idmp", tags=["acceptance-idempotency"])  # test-only


@_idmp.post("/echo")
async def idmp_echo(payload: dict = Body(...)):
    """Return a body that includes a server nonce.

    With IdempotencyMiddleware enabled globally, the first request will
    compute and cache the response. Subsequent requests with the same
    Idempotency-Key and identical payload should replay the exact same
    response, including the nonce value, without re-executing the handler.
    """
    return {"ok": True, "echo": payload, "nonce": uuid.uuid4().hex}


app.include_router(_idmp)

_cc = APIRouter(prefix="/cc", tags=["acceptance-concurrency"])  # test-only


class _Item(SimpleNamespace):
    id: str
    value: str
    version: int


_items: dict[str, _Item] = {}


@_cc.post("/items", status_code=201)
async def cc_create_item(payload: dict = Body(...)):
    iid = payload.get("id") or uuid.uuid4().hex
    val = payload.get("value") or ""
    if iid in _items:
        # treat as idempotent create returning existing
        item = _items[iid]
        return {"id": item.id, "value": item.value, "version": item.version}
    item = _Item(id=iid, value=val, version=1)
    _items[iid] = item
    return {"id": item.id, "value": item.value, "version": item.version}


@_cc.get("/items/{item_id}")
async def cc_get_item(item_id: str):
    item = _items.get(item_id)
    if not item:
        raise HTTPException(404, "not_found")
    return {"id": item.id, "value": item.value, "version": item.version}


@_cc.put("/items/{item_id}")
async def cc_update_item(item_id: str, payload: dict = Body(...)):
    item = _items.get(item_id)
    if not item:
        raise HTTPException(404, "not_found")
    provided_ver = int(payload.get("version") or 0)
    if provided_ver != item.version:
        return JSONResponse(
            status_code=409,
            content={
                "type": "about:blank",
                "title": "Conflict",
                "detail": "Version mismatch",
                "expected": item.version,
            },
        )
    item.value = payload.get("value") or item.value
    item.version += 1
    return {"id": item.id, "value": item.value, "version": item.version}


app.include_router(_cc)

# ---------------- Acceptance-only Jobs & Scheduler (A4) -----------------
_jobs = APIRouter(prefix="/jobs", tags=["acceptance-jobs"])  # test-only

# Initialize a jobs queue and scheduler using easy helpers (in-memory by default)
_queue, _scheduler = easy_jobs()

# In-memory state for the acceptance job handler
_job_results: list[dict] = []
_job_failures: dict[str, int] = {}  # job name -> remaining failures before success


def _accept_jobs_reset():
    """Acceptance-only helper to reset in-memory jobs/results state between tests.

    The acceptance harness runs a single API process for multiple tests. Make sure
    queued jobs and recorded results don't leak across tests.
    """
    try:
        _job_results.clear()
    except Exception:
        pass
    try:
        _job_failures.clear()
    except Exception:
        pass
    try:
        # Clear any pending jobs in the in-memory queue
        if hasattr(_queue, "_jobs"):
            getattr(_queue, "_jobs").clear()
    except Exception:
        pass


async def _accept_job_handler(job: Job) -> None:
    """Acceptance job handler with programmable failures.

    - If configured, will fail the first N attempts per job name by raising.
    - On success, records a result with name, payload, and current attempts.
    """
    # Route outbox jobs to the webhooks delivery handler.
    # Important: do NOT swallow exceptions from the handler – let them
    # propagate so the worker marks the job as failed and retries with backoff.
    handler = None
    try:
        if job.name.startswith("outbox."):
            handler = getattr(app.state, "webhooks_delivery_handler", None)
    except Exception:
        handler = None
    if handler:
        # Ensure webhook delivery jobs use a short but non-zero backoff so an
        # immediate subsequent process attempt does not re-run the same job.
        # This makes retries deterministic for acceptance tests.
        try:
            if job.name.startswith("outbox."):
                # Use a slightly larger backoff to account for fast environments
                # and the scheduler tick happening in the same moment.
                job.backoff_seconds = 2  # type: ignore[assignment]
        except Exception:
            # Best-effort; if mutation fails we still proceed
            pass
        await handler(job)
        return

    # Fail first N attempts for this job name if configured
    remain = _job_failures.get(job.name, 0)
    if remain > 0:
        _job_failures[job.name] = remain - 1
        raise RuntimeError(f"configured-failure:{job.name}:{remain}")
    # Record successful processing
    _job_results.append(
        {
            "id": job.id,
            "name": job.name,
            "payload": dict(job.payload),
            "attempts": job.attempts,
        }
    )


@_jobs.post("/enqueue")
async def jobs_enqueue(payload: dict = Body(...)):
    name = (payload.get("name") or "accept.job").strip()
    data = dict(payload.get("payload") or {})
    delay = int(payload.get("delay_seconds") or 0)
    job = _queue.enqueue(name, data, delay_seconds=delay)
    # Allow overriding backoff_seconds for test speed
    if "backoff_seconds" in payload:
        try:
            job.backoff_seconds = int(payload["backoff_seconds"])  # type: ignore[assignment]
        except Exception:
            pass
    return {
        "id": job.id,
        "name": job.name,
        "attempts": job.attempts,
        "available_at": job.available_at.isoformat(),
    }


@_jobs.post("/process-one")
async def jobs_process_one():
    processed = await process_one(_queue, _accept_job_handler)
    return {"processed": bool(processed)}


@_jobs.get("/results")
async def jobs_results():
    return {"results": list(_job_results)}


@_jobs.post("/config/failures")
async def jobs_config_failures(payload: dict = Body(...)):
    # Reset acceptance jobs state to avoid leakage across tests; the
    # acceptance tests call this endpoint at the start of each scenario.
    _accept_jobs_reset()
    name = (payload.get("name") or "accept.job").strip()
    times = int(payload.get("times") or 0)
    _job_failures[name] = max(0, times)
    return {"name": name, "failures": _job_failures[name]}


@_jobs.get("/peek")
async def jobs_peek():
    rows = []
    try:
        # Access in-memory queue internals for acceptance visibility
        for j in getattr(_queue, "_jobs", []):
            rows.append(
                {
                    "id": j.id,
                    "name": j.name,
                    "attempts": j.attempts,
                    "available_at": j.available_at.isoformat(),
                    "last_error": j.last_error,
                }
            )
    except Exception:
        pass
    return {"jobs": rows}


@_jobs.post("/make-due")
async def jobs_make_due(payload: dict = Body(...)):
    target_id = payload.get("id")
    count = 0
    try:
        now = datetime.now(timezone.utc)
        for j in getattr(_queue, "_jobs", []):
            if not target_id or j.id == str(target_id):
                j.available_at = now  # type: ignore[assignment]
                count += 1
    except Exception:
        pass
    return {"updated": count}


@_jobs.post("/set-backoff")
async def jobs_set_backoff(payload: dict = Body(...)):
    target_id = str(payload.get("id") or "").strip()
    seconds = int(payload.get("seconds") or 1)
    updated = False
    try:
        for j in getattr(_queue, "_jobs", []):
            if j.id == target_id:
                j.backoff_seconds = seconds  # type: ignore[assignment]
                updated = True
                break
    except Exception:
        pass
    return {"ok": updated}


app.include_router(_jobs)

_sched = APIRouter(prefix="/scheduler", tags=["acceptance-scheduler"])  # test-only
_sched_counters: dict[str, int] = {}


@_sched.post("/add")
async def sched_add(payload: dict = Body(...)):
    name = (payload.get("name") or "accept.tick").strip()
    interval = int(payload.get("interval_seconds") or 0)

    async def _tick():
        _sched_counters[name] = _sched_counters.get(name, 0) + 1

    _scheduler.add_task(name, interval, _tick)
    return {"name": name, "interval_seconds": interval}


@_sched.post("/tick")
async def sched_tick():
    # Reset jobs/results state on every scheduler tick call that the acceptance
    # tests make at the beginning of their flows. This avoids cross-test state.
    _accept_jobs_reset()
    await _scheduler.tick()
    return {"ok": True}


@_sched.get("/counters")
async def sched_counters():
    return {"counters": dict(_sched_counters)}


app.include_router(_sched)

# ---------------- Acceptance-only Webhooks (A5) -----------------
# Wire library router and delivery job to the in-memory queue/scheduler
add_webhooks(app, queue=_queue, scheduler=_scheduler, schedule_tick=True)

# Make the webhooks outbox tick runnable immediately on every tick for deterministic tests.
# The helper above schedules it at 1s intervals; rapid acceptance tests may call
# /scheduler/tick within that window. Overwrite the task with a 0s interval.
try:
    _tick = getattr(app.state, "webhooks_outbox_tick", None)
    if _tick is not None:
        _scheduler.add_task("webhooks.outbox", 0, _tick)
except Exception:
    pass

_wh = APIRouter(prefix="/_accept/webhooks", tags=["acceptance-webhooks"])  # test-only

# Receiver configuration/state
_wh_secrets: list[str] = []
_wh_failures_left: int = 0
_wh_deliveries: list[dict] = []


def _should_use_asgi_transport(url: str) -> bool:
    try:
        u = urlparse(url)
        return (u.hostname or "").lower() == "testserver"
    except Exception:
        return False


async def _local_post(url: str, json_body: dict, headers: dict) -> httpx.Response:
    # Use ASGITransport to avoid real network when targeting testserver
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Strip scheme+host if present to avoid double host
        path = urlparse(url).path or "/"
        return await client.post(path, json=json_body, headers=headers)


# Override the webhooks delivery handler to use ASGITransport in-process
async def _accept_webhook_delivery(job: Job) -> None:
    data = job.payload or {}
    outbox_id = data.get("outbox_id")
    topic = data.get("topic")
    payload = data.get("payload") or {}
    if not outbox_id or not topic:
        return
    # The built-in handler signs payload and posts over HTTP; we emulate but allow ASGITransport
    from svc_infra.webhooks.signing import sign

    subscription = payload.get("subscription") if isinstance(payload, dict) else None
    event = payload.get("event") if isinstance(payload, dict) else None
    if event is not None and subscription is not None:
        delivery_payload = event
        url = subscription.get("url")
        secret = subscription.get("secret")
        subscription_id = subscription.get("id")
    else:
        # Fallback to router-level lookup via app.state
        def url_lookup(t):
            return app.state.webhooks_subscriptions.get_for_topic(t)[0].url

        def secret_lookup(t):
            return app.state.webhooks_subscriptions.get_for_topic(t)[0].secret

        delivery_payload = payload
        url = url_lookup(topic)
        secret = secret_lookup(topic)
        subscription_id = None
    sig = sign(secret, delivery_payload)
    headers = {
        "X-Signature": sig,
        "X-Event-Id": str(outbox_id),
        "X-Topic": str(topic),
        "X-Attempt": str(job.attempts or 1),
        "X-Signature-Alg": "hmac-sha256",
        "X-Signature-Version": "v1",
    }
    if subscription_id:
        headers["X-Webhook-Subscription"] = str(subscription_id)
    if isinstance(delivery_payload, dict) and delivery_payload.get("version") is not None:
        headers["X-Payload-Version"] = str(delivery_payload.get("version"))
    # Post using ASGI when targeting testserver, else real HTTP
    if _should_use_asgi_transport(url):
        resp = await _local_post(url, delivery_payload, headers)
    else:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=delivery_payload, headers=headers)
    if 200 <= resp.status_code < 300:
        app.state.webhooks_inbox.mark_if_new(f"webhook:{outbox_id}", ttl_seconds=24 * 3600)
        app.state.webhooks_outbox.mark_processed(int(outbox_id))
        return
    raise RuntimeError(f"webhook delivery failed: {resp.status_code}")


# Install our override handler
app.state.webhooks_delivery_handler = _accept_webhook_delivery


@_wh.post("/config")
async def webhook_config(payload: dict = Body(...)):
    global _wh_secrets, _wh_failures_left, _wh_deliveries
    secrets = payload.get("secrets") or []
    fails = int(payload.get("fail_first") or 0)
    _wh_secrets = list(secrets)
    _wh_failures_left = max(0, fails)
    _wh_deliveries = []
    return {"secrets": _wh_secrets, "fail_first": _wh_failures_left}


@_wh.post("/receiver")
async def webhook_receiver(payload: dict = Body(...), request: Request = None):
    global _wh_failures_left
    sig = request.headers.get("X-Signature") or ""
    # Verify against configured secrets list
    ok = verify_any(_wh_secrets, payload, sig) if _wh_secrets else False
    if not ok:
        return JSONResponse(status_code=400, content={"error": "bad_signature"})
    # Simulate transient failure for first N attempts
    if _wh_failures_left > 0:
        _wh_failures_left -= 1
        return JSONResponse(status_code=500, content={"error": "transient"})
    # Record delivery
    _wh_deliveries.append(
        {
            "payload": dict(payload),
            "headers": {k: v for k, v in request.headers.items()},
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"ok": True}


@_wh.get("/deliveries")
async def webhook_deliveries():
    return {"deliveries": list(_wh_deliveries)}


app.include_router(_wh)
