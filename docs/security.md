# Security Configuration & Examples

This document summarizes the security posture of the framework and how to configure common features.

## Contents
- Password policy and breach checking
- Account lockout
- Sessions and refresh tokens (rotation + revocation)
- JWT key rotation
- Signed cookies
- CORS and security headers
- RBAC and ABAC
- MFA policy hooks

## Password policy and breach checking
- Enforced by password validators with a configurable policy.
- Breach checking uses the HIBP range API; can be toggled via settings.

Example (pseudo-config):
- AUTH_PASSWORD_MIN_LENGTH=12
- AUTH_PASSWORD_REQUIRE_SYMBOL=True
- AUTH_PASSWORD_BREACH_CHECK=True

## Account lockout
- Lockout uses exponential backoff with a cooldown cap.
- Attempts are tracked by user_id and/or IP hash.
- Login endpoint enforces IP-level pre-check and user+IP lockout; responds 429 with `Retry-After` when locked.

Operational notes:
- Ensure SQL backend is configured for `FailedAuthAttempt` persistence.
- Tune thresholds in `LockoutConfig` as needed.

## Sessions and refresh tokens
- Sessions are listed and revocable via session router endpoints.
- Refresh tokens are rotated; old tokens are invalidated by writing to a revocation list.

Operational notes:
- Store session and token records in a durable DB.
- Consider short access token TTLs with robust refresh handling.

## JWT key rotation
- Supports a primary secret plus `old_secrets` for seamless rotation.
- Set `AUTH_JWT__SECRET` and `AUTH_JWT__OLD_SECRETS` (comma-separated) to maintain a key window.

## Signed cookies
- HMAC-SHA256 cookie signing with primary and old keys for rotation.
- Verification checks signature and optional expiration (exp).

## CORS and security headers
- Strict CORS defaults (deny by default). Provide allowlist entries for trusted origins.
- Security headers middleware sets common protections (X-Frame-Options, X-Content-Type-Options, etc.).

## RBAC and ABAC
- RBAC decorators enforce role/permission checks.
- ABAC hooks evaluate resource ownership and attributes.

## MFA policy hooks
- Policy decides when MFA is required; login returns 401 with `MFA_REQUIRED` and a pre-token when applicable.

## Troubleshooting
- 429 on login: likely lockout. Inspect `Retry-After` and `FailedAuthAttempt` records.
- Token invalid after refresh: verify rotation is working and revocation list updates are present.
- Cookie verification errors: check signing keys and exp.
