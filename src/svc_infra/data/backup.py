from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class BackupHealthReport:
    ok: bool
    last_success: datetime | None
    retention_days: int | None
    message: str = ""


def verify_backups(
    *, last_success: datetime | None = None, retention_days: int | None = None
) -> BackupHealthReport:
    """Return a basic backup health report.

    In production, callers should plug a provider-specific checker and translate into this report.
    """
    if last_success is None:
        return BackupHealthReport(
            ok=False,
            last_success=None,
            retention_days=retention_days,
            message="no_backup_seen",
        )
    now = datetime.now(UTC)
    age_days = (now - last_success).total_seconds() / 86400.0
    ok = retention_days is None or age_days <= max(1, retention_days)
    return BackupHealthReport(ok=ok, last_success=last_success, retention_days=retention_days)


__all__ = ["BackupHealthReport", "verify_backups"]


def make_backup_verification_job(
    checker: Callable[[], BackupHealthReport],
    *,
    on_report: Callable[[BackupHealthReport], None] | None = None,
):
    """Return a callable suitable for scheduling in a job runner.

    The checker should perform provider-specific checks and return a BackupHealthReport.
    If on_report is provided, it will be invoked with the report.
    """

    def _job() -> BackupHealthReport:
        rep = checker()
        if on_report:
            on_report(rep)
        return rep

    return _job
