# ADR 0005: Data Lifecycle — Soft Delete, Retention, Erasure, Backups

Date: 2025-10-16
Status: Accepted

## Context
We need a coherent Data Lifecycle story in svc-infra that covers:
- Migrations & fixtures: simple way to run DB setup/migrations and load reference data.
- Soft delete conventions: consistent filtering and model scaffolding support.
- Retention policies: periodic purging of expired records per model/table.
- GDPR/PII erasure: queued workflow to scrub user-related data while preserving legal audit.
- Backups/PITR verification: a job that exercises restore checks or at least validates backup health signals.

Existing building blocks:
- Migrations CLI with end-to-end "setup-and-migrate" and new `sql seed` command for executing a user-specified seed callable.
  - Code: `src/svc_infra/cli/cmds/db/sql/alembic_cmds.py` (cmd_setup_and_migrate, cmd_seed)
- Soft delete support in repository and scaffold:
  - Repo filtering: `src/svc_infra/db/sql/repository.py` (soft_delete flags, `deleted_at` timestamp, optional active flag)
  - Model scaffolding: `src/svc_infra/db/sql/scaffold.py` (optional `deleted_at` field)
- Easy-setup helper to coordinate lifecycle bits:
  - `src/svc_infra/data/add.py` provides a startup hook to auto-migrate and optional callbacks for fixtures, retention jobs, and an erasure job.

Gaps:
- No standardized fixture loader contract beyond the callback surface.
- No built-in retention policy registry or purge execution job.
- No opinionated GDPR erasure workflow and audit trail.
- No backup/PITR verification job implementation.

## Decision
Introduce minimal, composable primitives that keep svc-infra flexible while providing a clear path to production-grade lifecycle.

1) Fixture Loader Contract
- Provide a simple callable signature for deterministic, idempotent fixture loading: `Callable[[], None | Awaitable[None]]`.
- Document best practices: UPSERT by natural keys, avoid random IDs, guard on existing rows.
- Expose via `add_data_lifecycle(on_load_fixtures=...)` (already available); add docs and tests.

2) Retention Policy Registry
- Define a registry API that allows services to register per-resource retention rules.
- Basic shape:
  - `RetentionPolicy(name: str, model: type, where: list[Any] | None, older_than_days: int, soft_delete_field: str = "deleted_at")`
  - A purge function computes a cutoff timestamp and issues DELETE or marks soft-delete fields.
- Execution model: a periodic job (via jobs scheduler) calls `run_retention_purge(registry)`.
- Keep SQL-only first; room for NoSQL extensions later.

3) GDPR Erasure Workflow
- Provide a single callable entrypoint `erase_principal(principal_id: str) -> None | Awaitable[None]`.
- Default strategy: enqueue a job that runs a configurable erasure plan composed of steps (delete/soft-delete/overwrite) across tables.
- Add an audit log entry per erasure request with outcome and timestamp (reuse `security.audit` helpers if feasible).
- Keep the plan provider pluggable so apps specify which tables/columns participate.

4) Backup/PITR Verification Job
- Define an interface `verify_backups() -> HealthReport` with a minimal default implementation that:
  - Queries the backup system or driver for last successful backup timestamp and retention window.
  - Emits metrics/logs and returns a structured status.
- Defer full "restore drill" capability; provide extension hook only.

## Interfaces
- Registry
  - `register_retention(policy: RetentionPolicy) -> None`
  - `run_retention_purge(session_factory, policies: list[RetentionPolicy]) -> PurgeReport`
- Erasure
  - `erase_principal(principal_id: str, plan: ErasurePlan, session_factory) -> ErasureReport`
- Fixtures
  - `load_fixtures()` as provided by caller via `add_data_lifecycle`.
- Backup
  - `verify_backups() -> BackupHealthReport`

## Alternatives Considered
- Heavy-weight DSL for retention and erasure: rejected for now; keep APIs Pythonic and pluggable.
- Trigger-level soft delete enforcement: skipped to avoid provider lock-in; enforced at repository and query layer.
- Full restore drill automation: out of scope for v1; introduce later behind provider integrations.

## Consequences
- Minimal surface that doesn't over-constrain adopters; provides default patterns and contracts.
- Requires additional test scaffolds and example docs to demonstrate usage.
- SQL-focused initial implementation; other backends can plug via similar interfaces.

## Rollout & Testing
- Add unit/integration tests for fixture loader, retention purge logic, and erasure workflow skeleton.
- Provide docs in `docs/database.md` with examples and operational guidance.

## References
- `src/svc_infra/db/sql/repository.py` soft-delete handling
- `src/svc_infra/db/sql/scaffold.py` deleted_at field scaffolding
- `src/svc_infra/data/add.py` data lifecycle helper
- `src/svc_infra/cli/cmds/db/sql/alembic_cmds.py` migrations & seed
