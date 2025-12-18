from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from svc_infra.data.backup import verify_backups

pytestmark = pytest.mark.data_lifecycle


def test_verify_backups_no_last_success():
    rep = verify_backups()
    assert rep.ok is False and rep.last_success is None


def test_verify_backups_ok_within_retention():
    last = datetime.now(UTC) - timedelta(hours=6)
    rep = verify_backups(last_success=last, retention_days=1)
    assert rep.ok is True and rep.last_success == last
