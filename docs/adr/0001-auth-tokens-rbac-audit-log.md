# ADR 0001: Auth Tokens, RBAC Permission Registry, and Audit Log Hash Chain

Status: Proposed
Date: 2025-10-14
Owner: Security & Auth Hardening Track

## Context
The framework currently includes:
- Role guards (`RequireRoles`) and a `roles_router` shortcut for protected endpoints.
- OAuth router with refresh endpoint (`/refresh`) persisting provider refresh tokens on account link models.
- Password policy validator (`validate_password`) without breach (HIBP) integration yet.
- No persistent session/device model, explicit refresh token rotation, or revocation list.
- No unified permission registry (roles are static strings) or ABAC hook.
- No audit log model providing append-only and tamper detection (hash chain) across security-sensitive events.

We require a consolidated design to implement: secure access/refresh token issuance & rotation, permission management (RBAC + ABAC), account/session lockouts, and an integrity-assured audit log.

## Requirements
1. Access tokens: short-lived (e.g. 15m) JWT (HS256/EdDSA) with tenant, subject, roles, issued_at, expires.
2. Refresh tokens: opaque, random 256-bit value (base64url) stored hashed (SHA-256) with rotation on each use; previous token placed on revocation list with grace window.
3. Session/device table: track (id, user_id, tenant_id, created_at, last_seen_at, user_agent, ip_hash, refresh_token_id current, revoked_at, reason).
4. Lockout service: after N failed auth attempts (e.g. 5) apply exponential cooldown; store attempts with timestamps.
5. RBAC permission registry: mapping role -> set(permission codes); Provide decorator ensuring permission present; role expansion cached.
6. ABAC predicate hook: resources can supply attribute dict; policy function evaluates dynamic predicates (e.g. owner match, plan tier check).
7. Audit log: append-only table with (id, ts, actor_id nullable, tenant_id, event_type, resource_ref, metadata JSON, hash, prev_hash). Enforce chain continuity; tamper detection test.
8. Key rolling: Support active + next signing key for JWT with kid header; script to promote next key.
9. HIBP breach check optional integration (k-anonymity SHA1 prefix search) gated by config.
10. CORS strict defaults: allowlist of origins, deny by default, expose minimal headers.

## Data Model Sketch
Tables (simplified columns):
- auth_session(id UUID, user_id UUID, tenant_id UUID, created_at, last_seen_at, ip_hash, user_agent, revoked_at, revoke_reason)
- refresh_token(id UUID, session_id FK, token_hash CHAR(64), created_at, rotated_at nullable, revoked_at nullable, revoke_reason, expires_at)
- refresh_token_revocation(id UUID, token_hash CHAR(64), revoked_at, reason)
- failed_auth_attempt(id UUID, user_id UUID, ts, ip_hash, outcome ENUM(success|failure))
- role_permission(role VARCHAR, permission VARCHAR, PRIMARY KEY(role, permission))
- audit_log(id BIGSERIAL, ts TIMESTAMPTZ, actor_id UUID NULL, tenant_id UUID, event_type VARCHAR, resource_ref VARCHAR NULL, metadata JSONB, hash CHAR(64), prev_hash CHAR(64) NULL)

## Token Flow
1. Login success -> create auth_session + initial refresh_token row (hashed).
2. Issue access JWT signed with active key (kid in header). Store no server state for access token.
3. Refresh endpoint: validate presented refresh token by hashing and lookup; if valid & not revoked/expired:
   - Create new refresh_token row (rotated) and mark previous rotated_at + insert into revocation table.
   - Return new access token + new refresh token cookie.
4. Revoke session: set revoked_at on auth_session, revoke all active refresh tokens.

## Rotation & Revocation Logic
- A refresh token is single-use. After refresh, old token hash placed into revocation set (fast lookup) for a grace period (e.g. 1 minute) then purged by scheduled job.
- Revocation list can live in Redis (token_hash : revoked_at) for fast deny before DB hit.

## Lockout Algorithm
- Maintain sliding window of recent failed attempts per user + ip_hash.
- If failures >= threshold in window, compute cooldown: base * 2^(fail_count - threshold). Store next_allowed_at.
- Provide guard that rejects login if now < next_allowed_at.

## RBAC & Permissions
- Define `permissions.py` with dictionary: PERMISSIONS = {"admin": {"user.read","user.write","billing.read",...}, "support": {...}}.
- Decorator `RequirePermission("user.write")` resolves user roles -> union permissions.
- Cache expansion in memory with TTL; invalidate on role-permission table change.

## ABAC Hook
- Provide function `check_abac(principal, action, resource_attrs)` returning bool; extensible registry of predicate functions.
- Combined guard: RequirePermission + ABAC predicate (if resource passed).

## Audit Log Hash Chain
- Each new audit_log row: compute `hash = SHA256(prev_hash || canonical_json(metadata) || event_type || ts || actor_id || tenant_id)`.
- `prev_hash` is last row's hash (per tenant or global sequence). Tamper detection: recompute chain; mismatch flags integrity error.

## Security Considerations
- Store only hashed refresh tokens (no plaintext retrieval).
- Use Argon2id for password hashing (memory-hard; configurable). Fallback to bcrypt if Argon2 not available.
- JWT signing: prefer EdDSA (Ed25519) if library support; HS256 fallback for simplicity (rotate secret key regularly).
- IP hashing: use SHA256 of IP + server salt to avoid storing raw IP.
- Rate-limit refresh endpoint and login attempts to mitigate abuse.

## Alternatives Considered
- Storing refresh tokens in Redis only (trade-off: persistence vs simplicity) -> rejected; need durable rotation history.
- Using blockchain-style merkle tree for audit logs -> complexity outweighs benefit; linear hash chain sufficient.

## Open Questions
- Multi-device concurrency: allow multiple active sessions? (Default yes, each with its own refresh token.)
- Tenant-level audit partitioning vs global chain? (Use per-tenant chain for scalability.)
- Permission registry dynamic editing UI needed? (Future admin scope.)

## Decision
Proceed with proposed models and flows. Implement incrementally: model schemas + hashing utilities -> session & refresh endpoints -> rotation logic -> RBAC/permission registry -> ABAC hook -> audit log chain -> lockout -> breach check integration.

## Migration & Rollout
1. Create tables (auth_session, refresh_token, refresh_token_revocation, failed_auth_attempt, role_permission, audit_log).
2. Backfill initial roles/permissions via migration seeder.
3. Introduce new login flow (feature flag) -> test -> cutover.
4. Enable hash-chain verification job & monitoring.

## Testing Strategy
- Unit: token hash & rotation, lockout calculation, permission expansion, audit hash continuity.
- Integration: login + refresh flows, revocation, ABAC predicate.
- Security: tamper test altering audit row should fail chain verification.

## Follow-ups
- Implement breach (HIBP) integration with prefix caching.
- Add CLI commands: rotate-jwt-key, list-sessions, revoke-session, verify-audit-chain.
