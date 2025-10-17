from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from svc_infra.data.backup import BackupHealthReport, make_backup_verification_job, verify_backups

pytestmark = pytest.mark.data_lifecycle


def test_make_backup_verification_job_calls_on_report():
    last = datetime.now(timezone.utc) - timedelta(hours=2)

    def checker():
        return verify_backups(last_success=last, retention_days=1)

    reports: list[BackupHealthReport] = []

    def on_report(rep: BackupHealthReport):
        reports.append(rep)

    job = make_backup_verification_job(checker, on_report=on_report)
    rep = job()

    assert rep.ok is True
    assert reports and reports[0] == rep
