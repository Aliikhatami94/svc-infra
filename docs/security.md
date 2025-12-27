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

---

## Production Security Checklist

Use this checklist before deploying to production:

### Authentication

- [ ] **Strong JWT secret**: `AUTH_JWT__SECRET` is at least 32 random bytes (not a dictionary word)
- [ ] **Token rotation ready**: `AUTH_JWT__OLD_SECRETS` configured for seamless key rotation
- [ ] **Short access token TTL**: 15-30 minutes recommended (`AUTH_JWT__TTL=900`)
- [ ] **Refresh token rotation**: Enabled with revocation on reuse
- [ ] **Session enumeration**: Users can list and revoke their sessions
- [ ] **MFA enforcement**: Required for admin roles (`AUTH_MFA__REQUIRED_ROLES=admin`)

### Passwords

- [ ] **Minimum length**: 12+ characters (`AUTH_PASSWORD_MIN_LENGTH=12`)
- [ ] **Complexity requirements**: Symbol/number required (`AUTH_PASSWORD_REQUIRE_SYMBOL=True`)
- [ ] **Breach checking**: HIBP enabled (`AUTH_PASSWORD_BREACH_CHECK=True`)
- [ ] **Account lockout**: Exponential backoff configured (`threshold=5, max_cooldown=3600`)

### Transport & Headers

- [ ] **HTTPS only**: All production traffic encrypted (TLS 1.2+)
- [ ] **HSTS enabled**: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- [ ] **CSP configured**: Content-Security-Policy restricts resource loading
- [ ] **X-Frame-Options**: Set to `DENY` to prevent clickjacking
- [ ] **Cookie security**: `httponly=true`, `secure=true`, `samesite=lax`
- [ ] **CORS restricted**: Only trusted origins in `CORS_ALLOW_ORIGINS`

### Secrets Management

- [ ] **No hardcoded secrets**: All secrets from environment or vault
- [ ] **Secret rotation plan**: Documented process for rotating all secrets
- [ ] **Secrets encrypted at rest**: Using `*_FILE` pattern or KMS
- [ ] **Audit access to secrets**: Logging who accesses secret values

### API Security

- [ ] **Rate limiting**: Per-tenant and global limits configured
- [ ] **Input validation**: Pydantic models for all request bodies
- [ ] **SQL injection**: Using parameterized queries (SQLAlchemy)
- [ ] **Request size limits**: Max body size configured in proxy/app
- [ ] **Timeout protection**: Request timeouts prevent slowloris

### Logging & Monitoring

- [ ] **Structured logging**: JSON format with correlation IDs
- [ ] **No secrets in logs**: Passwords, tokens, PII filtered
- [ ] **Audit trail**: Security events logged with hash-chain
- [ ] **Alerting**: 401/403 spikes trigger alerts
- [ ] **Log retention**: Minimum 90 days for compliance

---

## Attack/Defense Scenarios

### Credential Stuffing Attack

**Attack**: Attacker uses breached credentials from other sites to attempt login.

**Defenses**:
```python
from svc_infra.security.lockout import LockoutConfig, get_lockout_status, record_attempt
from svc_infra.security.hibp import check_password_breach

# 1. Rate limiting by IP
lockout_cfg = LockoutConfig(
    threshold=5,              # 5 failed attempts
    window_minutes=15,        # Within 15 minutes
    base_cooldown_seconds=30, # Start at 30s lockout
    max_cooldown_seconds=3600 # Max 1 hour lockout
)

@router.post("/login")
async def login(request: Request, creds: LoginRequest, session = Depends(get_session)):
    ip_hash = hashlib.sha256(request.client.host.encode()).hexdigest()[:16]

    # Check lockout
    status = await get_lockout_status(session, user_id=None, ip_hash=ip_hash, cfg=lockout_cfg)
    if status.locked:
        raise HTTPException(
            429,
            "Too many failed attempts",
            headers={"Retry-After": str(status.retry_after_seconds)}
        )

    user = await authenticate(session, creds.email, creds.password)
    if not user:
        await record_attempt(session, user_id=None, ip_hash=ip_hash, success=False)
        await session.commit()
        raise HTTPException(401, "Invalid credentials")

    # 2. Check if password was in a breach
    is_breached = await check_password_breach(creds.password)
    if is_breached:
        # Force password change on next login
        await flag_password_change_required(session, user.id)

    await record_attempt(session, user_id=user.id, ip_hash=ip_hash, success=True)
    return create_tokens(user)
```

### Session Hijacking

**Attack**: Attacker steals session token via XSS or network interception.

**Defenses**:
```python
# 1. Secure cookie configuration (automatic in svc-infra)
response.set_cookie(
    key="session",
    value=token,
    httponly=True,    # No JavaScript access
    secure=True,      # HTTPS only
    samesite="lax",   # CSRF protection
    max_age=3600,     # Short TTL
)

# 2. Session binding to fingerprint
def create_session_token(user_id: str, request: Request) -> str:
    fingerprint = hashlib.sha256(
        f"{request.headers.get('user-agent', '')}"
        f"{request.client.host}".encode()
    ).hexdigest()[:16]

    return jwt.encode({
        "sub": user_id,
        "fp": fingerprint,
        "iat": datetime.utcnow(),
    }, SECRET)

# 3. Validate fingerprint on each request
def validate_session(token: str, request: Request) -> bool:
    payload = jwt.decode(token, SECRET)
    expected_fp = hashlib.sha256(
        f"{request.headers.get('user-agent', '')}"
        f"{request.client.host}".encode()
    ).hexdigest()[:16]
    return payload.get("fp") == expected_fp
```

### SQL Injection

**Attack**: Attacker injects SQL via user input.

**Defenses**:
```python
# ❌ VULNERABLE: String concatenation
query = f"SELECT * FROM users WHERE email = '{user_input}'"

# ✅ SAFE: Parameterized query (SQLAlchemy)
stmt = select(User).where(User.email == user_input)
result = await session.execute(stmt)

# ✅ SAFE: Using text() with parameters
from sqlalchemy import text
stmt = text("SELECT * FROM users WHERE email = :email")
result = await session.execute(stmt, {"email": user_input})
```

### Cross-Site Request Forgery (CSRF)

**Attack**: Attacker tricks user into making authenticated requests.

**Defenses**:
```python
# 1. SameSite cookies (automatic)
# Cookie: session=...; SameSite=Lax

# 2. CSRF tokens for state-changing operations
from svc_infra.security.csrf import generate_csrf_token, validate_csrf_token

@router.get("/profile")
async def get_profile(request: Request):
    csrf_token = generate_csrf_token(request)
    return {"data": ..., "csrf_token": csrf_token}

@router.post("/profile")
async def update_profile(request: Request, body: ProfileUpdate):
    csrf_token = request.headers.get("X-CSRF-Token")
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(403, "Invalid CSRF token")
    # Process update

# 3. Custom header requirement
# Attacker cannot set custom headers in cross-origin requests
X-Requested-With: XMLHttpRequest
```

### Token Replay

**Attack**: Attacker intercepts and reuses a valid token.

**Defenses**:
```python
# 1. Short token TTL
ACCESS_TOKEN_TTL = 900  # 15 minutes

# 2. Refresh token rotation with revocation
async def refresh_tokens(refresh_token: str, session) -> TokenPair:
    payload = jwt.decode(refresh_token, SECRET)

    # Check if token was already used (rotation)
    if await is_token_revoked(session, payload["jti"]):
        # Token reuse detected - revoke all user's tokens
        await revoke_all_tokens_for_user(session, payload["sub"])
        raise HTTPException(401, "Token reuse detected - all sessions revoked")

    # Revoke old refresh token
    await revoke_token(session, payload["jti"])

    # Issue new token pair
    return create_token_pair(payload["sub"])

# 3. One-time use tokens for sensitive operations
async def generate_password_reset_token(user_id: str, session) -> str:
    token = secrets.token_urlsafe(32)
    await store_token(session, user_id, token, ttl=3600, one_time=True)
    return token
```

### Privilege Escalation

**Attack**: User attempts to access admin functionality.

**Defenses**:
```python
from svc_infra.security.permissions import RequirePermission, RequireRoles

# 1. Defense in depth - both role AND permission checks
@router.get(
    "/admin/users",
    dependencies=[
        RequireRoles("admin"),           # Role gate
        RequirePermission("user.read"),  # Permission gate
    ]
)
async def list_users():
    ...

# 2. ABAC for resource ownership
from svc_infra.security.permissions import RequireABAC, owns_resource

@router.delete(
    "/documents/{doc_id}",
    dependencies=[RequireABAC(
        permission="document.delete",
        predicate=owns_resource("owner_id"),
        resource_getter=get_document,
    )]
)
async def delete_document(doc_id: str):
    ...

# 3. Tenant isolation at data layer
from svc_infra.tenancy import TenantSqlService

class UserService(TenantSqlService[User]):
    # All queries automatically scoped to current tenant
    pass
```

---

## Penetration Testing Guide

### Scope Definition

Before testing, define:

| Category | In Scope | Out of Scope |
|----------|----------|--------------|
| **Authentication** | Login, MFA, password reset | Third-party OAuth providers |
| **Authorization** | RBAC, ABAC, tenant isolation | Admin impersonation (audit-only) |
| **API** | All REST endpoints | WebSocket (separate test) |
| **Infrastructure** | Application layer | Cloud provider infrastructure |

### Testing Methodology

#### 1. Reconnaissance

```bash
# Discover API endpoints
curl -s https://api.example.com/openapi.json | jq '.paths | keys'

# Enumerate users (should fail with 404, not 401)
for email in admin@example.com test@example.com; do
  curl -s -o /dev/null -w "%{http_code}" \
    "https://api.example.com/v1/auth/forgot-password" \
    -d "{\"email\": \"$email\"}"
done
```

#### 2. Authentication Testing

```bash
# Test lockout
for i in {1..10}; do
  curl -X POST https://api.example.com/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
done
# Expected: 429 after threshold

# Test JWT signature validation
# Modify token and replay
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIn0.SIGNATURE"
MODIFIED=$(echo $TOKEN | sed 's/user/admin/')
curl -H "Authorization: Bearer $MODIFIED" https://api.example.com/v1/profile
# Expected: 401
```

#### 3. Authorization Testing

```bash
# IDOR - Access other user's resources
curl -H "Authorization: Bearer $USER_TOKEN" \
  https://api.example.com/v1/users/OTHER_USER_ID/documents
# Expected: 403 or 404 (not 200)

# Privilege escalation
curl -X POST -H "Authorization: Bearer $USER_TOKEN" \
  https://api.example.com/admin/users
# Expected: 403

# Tenant isolation
curl -H "Authorization: Bearer $TENANT_A_TOKEN" \
  https://api.example.com/v1/resources?tenant_id=TENANT_B
# Expected: 403 or only TENANT_A resources
```

#### 4. Injection Testing

```bash
# SQL injection
curl "https://api.example.com/v1/search?q=test'%20OR%201=1--"
# Expected: 400 (validation error)

# Command injection
curl -X POST https://api.example.com/v1/export \
  -d '{"format": "; rm -rf /"}'
# Expected: 400

# Path traversal
curl "https://api.example.com/v1/files/..%2F..%2Fetc%2Fpasswd"
# Expected: 400 or 404
```

### Automated Testing Tools

```yaml
# Example OWASP ZAP configuration
zap:
  target: https://api.example.com
  authentication:
    type: http
    loginUrl: /v1/auth/login
    loginRequestData: '{"email":"test@example.com","password":"test123"}'
    tokenName: access_token
  rules:
    - id: 10020  # X-Frame-Options
    - id: 10021  # X-Content-Type-Options
    - id: 10038  # Content Security Policy
    - id: 40012  # Cross Site Scripting (Reflected)
    - id: 40014  # Cross Site Scripting (Persistent)
    - id: 40018  # SQL Injection
```

### Reporting Template

```markdown
## Finding: [SEVERITY] - Title

### Description
Brief description of the vulnerability.

### Affected Endpoint
`POST /v1/endpoint`

### Steps to Reproduce
1. Step one
2. Step two
3. Observe result

### Evidence
```
curl command or screenshot
```

### Impact
What an attacker could do.

### Remediation
Recommended fix.

### References
- OWASP reference
- CWE number
```

---

## Compliance Mapping

### SOC 2 Trust Service Criteria

| TSC | Control | svc-infra Feature |
|-----|---------|-------------------|
| **CC6.1** | Logical access controls | RBAC/ABAC permissions, `RequirePermission`, `RequireRoles` |
| **CC6.2** | Authentication | JWT tokens, MFA, OAuth, password policies |
| **CC6.3** | Access removal | Session revocation, `revoke_all_sessions()` |
| **CC6.6** | Encryption in transit | HTTPS enforcement, HSTS headers |
| **CC6.7** | Encryption at rest | `*_FILE` secrets, encrypted session data |
| **CC7.1** | System monitoring | Structured logging, audit trail |
| **CC7.2** | Anomaly detection | Rate limiting, lockout, alerting |

### HIPAA Security Rule

| Safeguard | Requirement | svc-infra Feature |
|-----------|-------------|-------------------|
| **Access Control** | Unique user identification | User IDs, JWT claims |
| **Access Control** | Automatic logoff | Session TTL, token expiration |
| **Audit Controls** | Activity logs | Hash-chain audit logs, `append_audit_event()` |
| **Integrity** | Authentication | JWT signature verification |
| **Transmission Security** | Encryption | HTTPS, TLS 1.2+ |

### GDPR Article Mapping

| Article | Requirement | svc-infra Feature |
|---------|-------------|-------------------|
| **Art. 5(1)(f)** | Integrity & confidentiality | Encryption, access controls, audit logs |
| **Art. 25** | Data protection by design | Tenant isolation, ABAC, minimal exposure |
| **Art. 30** | Records of processing | Audit log with hash-chain |
| **Art. 32** | Security of processing | RBAC, encryption, lockout, MFA |
| **Art. 33** | Breach notification | Audit trail for incident investigation |

### PCI DSS Requirements

| Requirement | Description | svc-infra Feature |
|-------------|-------------|-------------------|
| **8.2** | Strong authentication | MFA, password policies, JWT |
| **8.3** | MFA for admin access | `AUTH_MFA__REQUIRED_ROLES=admin` |
| **8.5** | Session timeouts | Token TTL, session expiration |
| **10.1** | Audit trails | Hash-chain audit logs |
| **10.2** | Automated audit trails | `append_audit_event()`, event types |
| **10.5** | Secure audit trails | Hash-chain tamper detection |

### Implementation Checklist by Framework

#### SOC 2 Type II
```python
# Required configuration
AUTH_JWT__TTL = 900                    # Short token TTL
AUTH_MFA__REQUIRED_ROLES = "admin"     # MFA for admins
AUTH_PASSWORD_MIN_LENGTH = 12
AUTH_PASSWORD_BREACH_CHECK = True

# Required code
from svc_infra.security.audit import append_audit_event

# Log all security-relevant events
await append_audit_event(
    session,
    actor_id=user.id,
    event_type="user.login.success",
    resource_ref=f"user:{user.id}",
    metadata={"ip": request.client.host, "user_agent": request.headers.get("user-agent")},
)
```

#### HIPAA
```python
# Required configuration
AUTH_JWT__TTL = 300                    # 5 minute tokens for PHI access
SESSION_IDLE_TIMEOUT = 900             # 15 minute idle timeout
AUDIT_RETENTION_DAYS = 2190            # 6 year retention

# Required: Log access to PHI
await append_audit_event(
    session,
    actor_id=user.id,
    event_type="phi.access",
    resource_ref=f"patient:{patient_id}",
    metadata={"fields_accessed": fields, "reason": "treatment"},
)
```

---

## Troubleshooting
- 429 on login: lockout active. Check `Retry-After` and `FailedAuthAttempt` rows.
- Token invalid post-refresh: confirm rotation + revocation writes.
- Cookie verification errors: check signing keys/exp.
