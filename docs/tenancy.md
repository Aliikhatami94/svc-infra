# Tenancy model and integration

This framework uses a soft-tenant isolation model by default: tenant_id is a column on tenant-scoped tables, and all queries are filtered by this value. Consumers can later adopt schema-per-tenant or DB-per-tenant strategies; the API surfaces remain compatible.

## How tenant is resolved
- `resolve_tenant_id(request)` looks up tenant id in this order:
  1) Global override hook (set via `add_tenancy(app, resolver=...)`)
  2) Auth identity (user.tenant_id or api_key.tenant_id) when auth is enabled
  3) `X-Tenant-Id` request header
  4) `request.state.tenant_id`

Use `TenantId` dependency to require it in routes, and `OptionalTenantId` to access it if present.

## Enforcement in data layer
- Wrap services with `TenantSqlService` to automatically:
  - Apply `WHERE model.tenant_id == <tenant>` on list/get/update/delete/search/count.
  - Inject `tenant_id` upon create when the model has the tenant field.

## Tenant-aware CRUD router
- When defining a `SqlResource`, set `tenant_field="tenant_id"` to mount a tenant-aware CRUD router. All endpoints will require `TenantId` and enforce scoping.

## Per-tenant rate limits / quotas
- Global middleware and per-route dependency support tenant-aware policies:
  - `scope_by_tenant=True` puts requests in independent buckets per tenant.
  - `limit_resolver(request, tenant_id)` lets you return dynamic limits (e.g., plan-based quotas).

## Export a tenant’s data (SQL)
- CLI command: `sql export-tenant`
  - Example:
    - `python -m svc_infra.cli sql export-tenant items --tenant-id t1 --output out.json`
  - Flags:
    - `--tenant-id` (required), `--tenant-field` (default `tenant_id`), `--limit` (optional), `--database-url` (or set `SQL_URL`).

## Migration to other isolation strategies
- Schema-per-tenant or DB-per-tenant can be layered by adapting the session factory or repository to select the schema/DB based on `tenant_id`. Your application code that relies on `TenantId` and tenant-aware services/routers remains the same.
