"""Data lifecycle module for backup verification, retention, and GDPR erasure.

This module provides data lifecycle management primitives:

- **add_data_lifecycle**: FastAPI integration for auto-migration and fixtures
- **Backup**: Backup health verification utilities
- **Retention**: Data retention policies and purge execution
- **Erasure**: GDPR-compliant data erasure workflows
- **Fixtures**: Fixture loading with run-once semantics

Example:
    from fastapi import FastAPI
    from svc_infra.data import add_data_lifecycle, make_on_load_fixtures

    app = FastAPI()

    # Enable auto-migration and fixture loading
    add_data_lifecycle(
        app,
        auto_migrate=True,
        on_load_fixtures=make_on_load_fixtures(load_seed_data),
    )

    # Define retention policies
    from svc_infra.data import RetentionPolicy, run_retention_purge

    policies = [
        RetentionPolicy(name="old_logs", model=AuditLog, older_than_days=90),
        RetentionPolicy(name="expired_tokens", model=RefreshToken, older_than_days=30),
    ]

    # Run in a scheduled job
    affected = await run_retention_purge(session, policies)

    # GDPR erasure
    from svc_infra.data import ErasurePlan, ErasureStep, run_erasure

    plan = ErasurePlan(steps=[
        ErasureStep(name="anonymize_user", run=anonymize_user_data),
        ErasureStep(name="delete_logs", run=delete_user_logs),
    ])
    await run_erasure(session, principal_id="user_123", plan=plan)

See Also:
    - docs/data-lifecycle.md for detailed documentation
"""

from __future__ import annotations

# FastAPI integration
from .add import add_data_lifecycle

# Backup verification
from .backup import BackupHealthReport, make_backup_verification_job, verify_backups

# GDPR erasure
from .erasure import ErasurePlan, ErasureStep, run_erasure

# Fixture loading
from .fixtures import make_on_load_fixtures, run_fixtures

# Retention policies
from .retention import RetentionPolicy, purge_policy, run_retention_purge

__all__ = [
    # FastAPI integration
    "add_data_lifecycle",
    # Backup
    "BackupHealthReport",
    "verify_backups",
    "make_backup_verification_job",
    # Retention
    "RetentionPolicy",
    "purge_policy",
    "run_retention_purge",
    # Erasure
    "ErasureStep",
    "ErasurePlan",
    "run_erasure",
    # Fixtures
    "run_fixtures",
    "make_on_load_fixtures",
]
