# Data Lifecycle

This guide covers fixtures (reference data), retention policies (soft/hard delete), GDPR erasure, and backup verification.

## Quickstart

- Fixtures:
  - Use `run_fixtures([...])` for ad-hoc loads.
  - Or wire a one-time loader with `make_on_load_fixtures(fn, run_once_file)`, then `add_data_lifecycle(app, on_startup=[on_load])`.
- Retention:
  - Define `RetentionPolicy(name, model, older_than_days, soft_delete_field|None, hard_delete=False)`.
  - Execute manually with `await run_retention_purge(session, [policy,...])` or schedule via your jobs runner.
- Erasure:
  - Compose an `ErasurePlan([ErasureStep(name, func), ...])` where functions accept `(session, principal_id)` and may be async.
  - Run with `await run_erasure(session, principal_id, plan, on_audit=callable)`; `on_audit` receives `(event, context)`.
- Backups:
  - `verify_backups(last_success: datetime|None, retention_days: int)` returns a `BackupHealthReport`.
  - Wrap as a job: `make_backup_verification_job(checker, on_report=callback)`.

## APIs

- `fixtures.py`:
  - `run_fixtures(callables: Iterable[Callable]) -> Awaitable[None]`
  - `make_on_load_fixtures(*fns, run_once_file: str | None = None) -> Callable[[], Awaitable[None]]`
- `retention.py`:
  - `RetentionPolicy(name, model, older_than_days, soft_delete_field: str | None, hard_delete: bool = False)`
  - `run_retention_purge(session, policies: Sequence[RetentionPolicy]) -> Awaitable[int]`
- `erasure.py`:
  - `ErasureStep(name: str, func: Callable)`
  - `ErasurePlan(steps: Sequence[ErasureStep])`
  - `run_erasure(session, principal_id: str, plan: ErasurePlan, on_audit: Callable | None = None) -> Awaitable[int]`
- `backup.py`:
  - `BackupHealthReport(ok: bool, last_success: datetime | None, reason: str | None)`
  - `verify_backups(last_success: datetime | None = None, retention_days: int = 1) -> BackupHealthReport`
  - `make_backup_verification_job(checker: Callable[[], BackupHealthReport], on_report: Callable[[BackupHealthReport], None] | None = None) -> Callable[[], BackupHealthReport]`

## Scheduling

Use the jobs helpers to run retention and backup checks periodically. Example schedule JSON (via JOBS_SCHEDULE_JSON):

```json
[
  {"name": "retention-purge", "interval": "6h", "handler": "your.module:run_retention"},
  {"name": "backup-verify",  "interval": "12h", "handler": "your.module:verify_backups_job"}
]
```

## Notes

- Soft delete expects a `deleted_at` column and optionally an `is_active` flag in repositories.
- `run_fixtures` and erasure steps support async functions seamlessly.
- `add_data_lifecycle` already awaits async fixture loaders and uses lifespan instead of deprecated startup events.
