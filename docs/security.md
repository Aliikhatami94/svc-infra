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

## RBAC and ABAC
- RBAC decorators guard endpoints by role/permission.
- ABAC evaluates resource ownership and attributes (e.g., `owns_resource`).

## MFA policy hooks
- Policy decides when MFA is required; login returns 401 with `MFA_REQUIRED` and a pre-token when applicable.

## Troubleshooting
- 429 on login: lockout active. Check `Retry-After` and `FailedAuthAttempt` rows.
- Token invalid post-refresh: confirm rotation + revocation writes.
- Cookie verification errors: check signing keys/exp.
