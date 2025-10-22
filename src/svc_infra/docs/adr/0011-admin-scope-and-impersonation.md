# 0011 — Admin scope, permissions, and impersonation

## Context
- The codebase already provides RBAC/permission helpers: `RequireRoles`, `RequirePermission`, ABAC via `RequireABAC`/`owns_resource`.
- The central permission registry maps roles → permissions (`svc_infra.security.permissions.PERMISSION_REGISTRY`). Notably, the `admin` role includes: `user.read`, `user.write`, `billing.read`, `billing.write`, and `security.session.{list,revoke}`.
- Acceptance tests demonstrate an “admin-only” route guarded by `RequirePermission("user.write")` and temporary role override to `admin`.
- There is no dedicated admin API surface yet, and no impersonation flow; observability docs mention an optional route classifier that can label routes like `public|internal|admin`.

## Goals
- Define a consistent approach for admin-only surfaces and permission alignment.
- Establish minimal permissions needed for admin operations, including impersonation.
- Outline an impersonation flow with security and audit guardrails.
- Prepare for an easy integration helper (`add_admin`) without implementing it yet.

## Non-goals
- Implement admin endpoints or impersonation logic in this ADR.
- Replace existing permissions/guards — this ADR aligns and extends them.

## Decisions

1) Permissions alignment and additions
- Keep permissions as the canonical guard unit; roles remain a mapping to permissions.
- Extend the registry with a dedicated permission for impersonation:
  - `admin.impersonate`
- Keep existing entries (`security.session.{list,revoke}` etc.) as-is.
- Recommended role → permission mapping updates:
  - `admin`: add `admin.impersonate` (retains existing permissions).
  - `auditor`: keep `audit.read` (already present) and may expand in the future.

2) Admin router pattern
- Provide an admin-only router pattern that layers role and permission checks consistently:
  - Top-level: role gate via `RequireRoles("admin")` to reflect the “admin area”.
  - Endpoint-level: permission gates via `RequirePermission(...)` for specific operations.
- Rationale: roles communicate the coarse-grained area; fine-grained actions are enforced by permissions.
- A future helper `admin_router()` can wrap `roles_router("admin")` (from `api.fastapi.dual.protected`) for ergonomic mounting.

3) Impersonation flow (design)
- Endpoints:
  - `POST /admin/impersonate/start` — body: `{ user_id, reason }`; requires `admin.impersonate`.
  - `POST /admin/impersonate/stop` — ends the session.
- Mechanics:
  - When starting, issue a short-lived, signed impersonation token (or set a dedicated cookie) that encodes: original admin principal id, target user id, issued-at, expires-at, and nonce.
  - Downstream identity resolution should reflect the impersonated user for request handling, while preserving the original admin as the "actor" for auditing.
  - Stopping invalidates the token/cookie (server-side revocation list or versioned secret), and subsequent requests fall back to the admin’s own identity.
- Safety guardrails:
  - Always require `admin.impersonate`.
  - Enforce explicit `reason` and capture request fingerprint (ip hash, user-agent) with the event.
  - Limit scope by tenant/org if applicable; optionally block actions explicitly marked non-impersonable.
  - Set short TTL (e.g., 15 minutes) with sliding refresh disabled.

4) Audit logging
- Emit structured audit events for impersonation lifecycle:
  - `admin.impersonation.started` with actor, target, reason, ip hash, user-agent, and expiry.
  - `admin.impersonation.stopped` with actor, target, and termination reason (expired/manual).
- Implementation options (future):
  - Minimal: log via the existing logging setup (structured logger, e.g., `logger.bind(...).info("audit", ...)`).
  - Preferred: emit to an audit outbox/table or webhook channel for retention and cross-system visibility.

5) Observability and route classification
- Encourage passing a `route_classifier` that labels admin routes as `admin` (e.g., for `/admin` base path) so metrics/SLO dashboards can split traffic into `public|internal|admin` classes.

## Consequences
- Clear, documented permissions and flow for admin-only features.
- Minimal surface to add later: `admin_router()` and `add_admin(app, ...)` helper that mounts admin routes and wires impersonation endpoints + audit hooks.
- Tests to plan when implementing:
  - Role vs permission gating behavior on /admin routes.
  - Impersonation start/stop lifecycle and audit emission.
  - Ownership checks that permit admin bypass where intended (e.g., session revocation).

## Follow-ups
- Update the permission registry to include `admin.impersonate` (and map into `admin`).
- Implement `admin_router()` and the `add_admin` helper following this ADR.
- Add admin acceptance tests and documentation for guardrails and operational guidance.
