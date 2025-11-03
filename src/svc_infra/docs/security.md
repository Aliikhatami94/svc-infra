# Security: Configuration & Examples

This guide covers the security primitives built into svc-infra and how to wire them:

> ℹ️ Environment variables for the auth/security helpers are catalogued in [Environment Reference](environment.md).

- Password policy and breach checking
- Account lockout (exponential backoff)
- Sessions and refresh tokens (rotation + revocation)
- JWT key rotation
- Signed cookies
- CORS and security headers
- RBAC and ABAC
- MFA policy hooks

Module map (examples reference these):
- `svc_infra.security.lockout` (LockoutConfig, compute_lockout, record_attempt, get_lockout_status)
- `svc_infra.security.signed_cookies` (sign_cookie, verify_cookie)
- `svc_infra.security.audit` and `security.audit_service` (hash-chain audit logs)
- `svc_infra.api.fastapi.auth.gaurd` (password login with lockout checks)
- `svc_infra.api.fastapi.auth.routers.*` (sessions, oauth routes, etc.)
- `svc_infra.api.fastapi.auth.settings.get_auth_settings` (cookie + token settings)
- `svc_infra.api.fastapi.middleware.security_headers` and CORS setup (strict defaults)

## Password policy and breach checking
- Enforced by validators with a configurable policy.
- Breach checking uses the HIBP k-Anonymity range API; can be toggled via settings.

Example toggles (pseudo-config):
- `AUTH_PASSWORD_MIN_LENGTH=12`
- `AUTH_PASSWORD_REQUIRE_SYMBOL=True`
- `AUTH_PASSWORD_BREACH_CHECK=True`

## Account lockout
- Exponential backoff with a max cooldown cap to deter credential stuffing.
- Attempts tracked by user_id and/or IP hash.
- Login endpoint blocks with 429 + `Retry-After` during cooldown.

Key API (from `svc_infra.security.lockout`):
- `LockoutConfig(threshold=5, window_minutes=15, base_cooldown_seconds=30, max_cooldown_seconds=3600)`
- `compute_lockout(fail_count, cfg)` → `LockoutStatus(locked, next_allowed_at, failure_count)`
- `record_attempt(session, user_id, ip_hash, success)`
- `get_lockout_status(session, user_id, ip_hash, cfg)`

Login integration (simplified):
```python
from svc_infra.security.lockout import get_lockout_status, record_attempt

# Compute ip_hash from request.client.host
status = await get_lockout_status(session, user_id=None, ip_hash=ip_hash)
if status.locked:
		raise HTTPException(429, headers={"Retry-After": ..})

user = await user_manager.user_db.get_by_email(email)
if not user:
		await record_attempt(session, user_id=None, ip_hash=ip_hash, success=False)
		raise HTTPException(400, "LOGIN_BAD_CREDENTIALS")
```

## Sessions and refresh tokens
- Sessions are enumerable and revocable via the sessions router.
- Refresh tokens are rotated; old tokens are invalidated via a revocation list.

Operational notes:
- Persist sessions/tokens in a durable DB.
- Favor short access token TTLs if refresh flow is robust.

## JWT key rotation
- Primary secret plus `old_secrets` allow seamless rotation.
- Set environment variables:
	- `AUTH_JWT__SECRET="..."`
	- `AUTH_JWT__OLD_SECRETS="old1,old2"`

## Signed cookies
Module: `svc_infra.security.signed_cookies`

```python
from svc_infra.security.signed_cookies import sign_cookie, verify_cookie

sig = sign_cookie({"sub": "user-123"}, secret="k1", exp_seconds=3600)
payload = verify_cookie(sig, secret="k1", old_secrets=["k0"])  # returns dict
```

## CORS and security headers
- Strict CORS defaults (deny by default). Provide allowlist entries.
- Security headers middleware sets common protections (X-Frame-Options, X-Content-Type-Options, etc.).

Use `svc_infra.security.add.add_security` to install the default middlewares on any
FastAPI app. By default it adds:

- `SecurityHeadersMiddleware` with practical defaults:
  - **Content-Security-Policy**: Allows same-origin resources, inline styles/scripts, data URI images, and HTTPS images. Blocks external scripts and framing.
  - **Strict-Transport-Security**: Forces HTTPS with long max-age and subdomain support
  - **X-Frame-Options**: Blocks framing (DENY)
  - **X-Content-Type-Options**: Prevents MIME sniffing (nosniff)
  - **Referrer-Policy**: Limits referrer leakage
  - **X-XSS-Protection**: Disabled (CSP is the modern protection)
- A strict `CORSMiddleware` that only enables CORS when origins are provided (via
  parameters or environment variables such as `CORS_ALLOW_ORIGINS`).

The default CSP policy is:
```
default-src 'self';
script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
img-src 'self' data: https:;
connect-src 'self';
font-src 'self' https://cdn.jsdelivr.net;
frame-ancestors 'none';
base-uri 'self';
form-action 'self'
```

This works out-of-the-box for most web applications, including FastAPI's built-in documentation (Swagger UI, ReDoc), while maintaining strong security.

The helper also supports optional toggles so you can match the same cookie and
header configuration that `setup_service_api` uses.

```python
from fastapi import FastAPI

from svc_infra.security.add import add_security

app = FastAPI()

add_security(
    app,
    cors_origins=["https://app.example.com"],
    headers_overrides={"Content-Security-Policy": "default-src 'self'; script-src 'self'"},  # Stricter CSP
    install_session_middleware=True,  # adds Starlette's SessionMiddleware
)
```

Environment variables (applied when parameters are omitted):

| Variable | Purpose |
| --- | --- |
| `CORS_ALLOW_ORIGINS` | Comma-separated CORS origins (e.g. `https://app.example.com, https://admin.example.com`) |
| `CORS_ALLOW_METHODS` | Allowed HTTP methods (defaults to `*`) |
| `CORS_ALLOW_HEADERS` | Allowed headers (defaults to `*`) |
| `CORS_ALLOW_ORIGIN_REGEX` | Regex used when matching origins (ignored if not set) |
| `CORS_ALLOW_CREDENTIALS` | Toggle credentials support (`true` / `false`) |
| `SESSION_COOKIE_NAME` | Session cookie name (defaults to `svc_session`) |
| `SESSION_COOKIE_MAX_AGE_SECONDS` | Max age for the session cookie (defaults to `14400`) |
| `SESSION_COOKIE_SAMESITE` | SameSite policy (`lax` by default) |
| `SESSION_COOKIE_SECURE` | Force the session cookie to be HTTPS-only |
| `SESSION_SECRET` | Secret key for Starlette's SessionMiddleware |

When your service already uses `setup_service_api`, call `add_security` after
building the parent app if you need additional overrides while keeping the
defaults intact:

```python
from svc_infra.api.fastapi.setup import setup_service_api
from svc_infra.security.add import add_security

app = setup_service_api(...)

add_security(
    app,
    headers_overrides={"Strict-Transport-Security": "max-age=63072000; includeSubDomains"},
    enable_hsts_preload=False,
)
```

## RBAC and ABAC
- RBAC decorators guard endpoints by role/permission.
- ABAC evaluates resource ownership and attributes (e.g., `owns_resource`).

## MFA policy hooks
- Policy decides when MFA is required; login returns 401 with `MFA_REQUIRED` and a pre-token when applicable.

## Troubleshooting
- 429 on login: lockout active. Check `Retry-After` and `FailedAuthAttempt` rows.
- Token invalid post-refresh: confirm rotation + revocation writes.
- Cookie verification errors: check signing keys/exp.
