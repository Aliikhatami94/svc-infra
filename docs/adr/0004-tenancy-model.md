# ADR-0004: Tenancy Model and Enforcement

Date: 2025-10-15

Status: Proposed

## Context

The framework needs a consistent, ergonomic multi-tenant story across modules (API scaffolding, SQL/Mongo persistence, auth/security, payments, jobs, webhooks). Existing patterns already reference `tenant_id` in many places (payments models and service, audit/session models, SQL/Mongo scaffolds). However, enforcement and app ergonomics were not unified.

## Decision

Adopt a default "soft-tenant" isolation model via a `tenant_id` column and centralized enforcement primitives:

- Resolution: `resolve_tenant_id` and `require_tenant_id` FastAPI dependencies in `api.fastapi.tenancy.context`. Resolution order: override hook → identity (user/api_key) → `X-Tenant-Id` header → `request.state.tenant_id`.
- Enforcement in SQL: `TenantSqlService(SqlService)` that scopes list/get/update/delete/search/count with a `where` clause and injects `tenant_id` on create when the model supports it. Repository methods accept optional `where` filters.
- Router ergonomics: `make_tenant_crud_router_plus_sql` which requires `TenantId` and uses `TenantSqlService` under the hood. This keeps route code simple while enforcing scoping.
- Extensibility: `set_tenant_resolver` hook to override resolution logic per app; `tenant_field` parameter to support custom column names. Future: schema-per-tenant or db-per-tenant via alternate repository/service implementations.

## Alternatives considered

1) Enforce tenancy at the ORM layer (SQLAlchemy events/session) – rejected for clarity and testability; we prefer explicit service/dep composition.
2) Global middleware that rewrites queries – rejected due to SQLAlchemy complexity and opacity.
3) Only rely on developers to remember filters – rejected due to footguns.

## Consequences

- Clear default behavior with escape hatches. Minimal changes for consumers using CRUD builders and SqlService.
- Requires models to include an optional or required `tenant_id` column for scoping.
- Non-SQL stores should add equivalent wrappers; Mongo scaffolds already include `tenant_id` fields and can mirror these patterns later.

## Implementation Notes

- New modules: `api.fastapi.tenancy.context`, `db.sql.tenant`. Repository updated to accept `where` filters.
- CRUD router extended with `make_tenant_crud_router_plus_sql` to require `TenantId`.
- Tests added: `tests/tenancy/*` for resolution and service scoping.

## Open Items

- Per-tenant quotas & rate limit overrides (tie into rate limit dependency/middleware via a resolver that returns per-tenant config).
- Export tenant CLI (dump/import data for a specific tenant).
- Docs: isolation guidance (column vs schema vs db), migration guidance.
