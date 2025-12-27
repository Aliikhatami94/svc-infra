# Data Lifecycle Management

**svc-infra** provides comprehensive data lifecycle management: fixtures for reference data, retention policies for cleanup, GDPR erasure workflows, and backup verification.

---

## Quick Start

```python
from fastapi import FastAPI
from svc_infra.data.add import add_data_lifecycle
from svc_infra.data.fixtures import make_on_load_fixtures
from svc_infra.data.retention import RetentionPolicy

app = FastAPI()

# Auto-migrate and load fixtures on startup
add_data_lifecycle(
    app,
    auto_migrate=True,
    on_load_fixtures=make_on_load_fixtures(
        load_default_categories,
        load_admin_users,
        run_once_file=".fixtures_loaded",
    ),
)
```

---

## Fixtures (Reference Data)

Load initial/reference data on application startup with idempotency support.

### Basic Usage

```python
from svc_infra.data.fixtures import run_fixtures, make_on_load_fixtures

# Define fixture loaders
async def load_categories(session):
    """Load default product categories."""
    defaults = [
        {"id": "electronics", "name": "Electronics"},
        {"id": "clothing", "name": "Clothing"},
        {"id": "home", "name": "Home & Garden"},
    ]
    for cat in defaults:
        await session.merge(Category(**cat))
    await session.commit()

async def load_admin_user(session):
    """Create default admin user."""
    admin = await session.get(User, "admin")
    if not admin:
        admin = User(id="admin", email="admin@example.com", role="admin")
        session.add(admin)
        await session.commit()

# Run manually
await run_fixtures([load_categories, load_admin_user])
```

### Idempotent Fixtures

Use a sentinel file to ensure fixtures run only once:

```python
await run_fixtures(
    [load_categories, load_admin_user],
    run_once_file=".fixtures_loaded",
)
# Creates .fixtures_loaded on success
# Subsequent calls skip if file exists
```

### Startup Integration

```python
from svc_infra.data.fixtures import make_on_load_fixtures
from svc_infra.data.add import add_data_lifecycle

# Create startup fixture loader
on_load = make_on_load_fixtures(
    load_categories,
    load_admin_user,
    load_feature_flags,
    run_once_file=".fixtures_loaded",
)

add_data_lifecycle(app, on_load_fixtures=on_load)
```

### Environment-Specific Fixtures

```python
import os

def load_fixtures_for_env():
    """Load fixtures based on environment."""
    env = os.getenv("ENV", "development")

    loaders = [load_default_config]

    if env == "development":
        loaders.extend([load_test_users, load_sample_data])
    elif env == "staging":
        loaders.extend([load_qa_users])
    # Production: only default config

    return loaders

add_data_lifecycle(
    app,
    on_load_fixtures=make_on_load_fixtures(
        *load_fixtures_for_env(),
        run_once_file=f".fixtures_{os.getenv('ENV', 'dev')}_loaded",
    ),
)
```

### Fixture Best Practices

```python
# ✅ Good: Idempotent fixtures using merge/upsert
async def load_settings(session):
    for setting in DEFAULT_SETTINGS:
        await session.merge(Setting(**setting))
    await session.commit()

# ✅ Good: Check before insert
async def load_admin(session):
    if not await session.get(User, "admin"):
        session.add(User(id="admin", ...))
        await session.commit()

# ❌ Bad: Will fail on duplicate
async def load_data(session):
    session.add(Category(id="electronics", ...))  # Fails if exists!
    await session.commit()
```

---

## Retention Policies

Automatically clean up old data based on configurable retention periods.

### Defining Policies

```python
from svc_infra.data.retention import RetentionPolicy

# Soft delete logs older than 30 days
log_retention = RetentionPolicy(
    name="audit-logs",
    model=AuditLog,
    older_than_days=30,
    soft_delete_field="deleted_at",  # Column to set timestamp
    hard_delete=False,
)

# Hard delete temporary data older than 7 days
temp_retention = RetentionPolicy(
    name="temp-files",
    model=TemporaryUpload,
    older_than_days=7,
    soft_delete_field=None,
    hard_delete=True,  # Actually DELETE rows
)

# With extra filtering conditions
session_retention = RetentionPolicy(
    name="expired-sessions",
    model=Session,
    older_than_days=90,
    extra_where=[Session.is_active == False],
    hard_delete=True,
)
```

### Running Purges

```python
from svc_infra.data.retention import run_retention_purge

# Manual execution
async def purge_old_data(session):
    policies = [log_retention, temp_retention, session_retention]
    affected = await run_retention_purge(session, policies)
    print(f"Purged {affected} rows")
```

### Scheduled Purges

Integrate with the jobs system for automatic cleanup:

```python
from svc_infra.jobs import JobQueue

async def retention_job():
    """Scheduled job to run retention purges."""
    async with get_session() as session:
        affected = await run_retention_purge(session, [
            log_retention,
            temp_retention,
            session_retention,
        ])
        logger.info(f"Retention purge: {affected} rows affected")
        return affected

# Register with job scheduler
queue.schedule(
    name="retention-purge",
    handler=retention_job,
    interval_hours=6,
)
```

### Soft Delete Pattern

Models should include soft delete columns:

```python
from sqlalchemy import Column, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase

class SoftDeleteMixin:
    deleted_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)

class AuditLog(Base, SoftDeleteMixin):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    action = Column(String)
    created_at = Column(DateTime, server_default=func.now())
```

### Retention in CRUD Repositories

```python
from svc_infra.db.sql import SqlRepository

class AuditLogRepository(SqlRepository):
    model = AuditLog

    async def list_active(self, session, *, limit: int, offset: int):
        """List only non-deleted logs."""
        return await self.list(
            session,
            limit=limit,
            offset=offset,
            where=[AuditLog.deleted_at.is_(None)],
        )
```

---

## GDPR Erasure

Comply with data subject deletion requests with composable erasure plans.

### Defining Erasure Steps

```python
from svc_infra.data.erasure import ErasureStep, ErasurePlan

# Individual erasure operations
async def erase_user_profile(session, principal_id: str) -> int:
    """Delete user profile data."""
    stmt = delete(UserProfile).where(UserProfile.user_id == principal_id)
    result = await session.execute(stmt)
    return result.rowcount

async def erase_user_orders(session, principal_id: str) -> int:
    """Anonymize order records (required for accounting)."""
    stmt = (
        update(Order)
        .where(Order.user_id == principal_id)
        .values(
            user_id=None,
            email="[REDACTED]",
            name="[REDACTED]",
            address="[REDACTED]",
        )
    )
    result = await session.execute(stmt)
    return result.rowcount

async def erase_user_comments(session, principal_id: str) -> int:
    """Delete all user comments."""
    stmt = delete(Comment).where(Comment.author_id == principal_id)
    result = await session.execute(stmt)
    return result.rowcount

async def erase_user_account(session, principal_id: str) -> int:
    """Finally delete the user account."""
    stmt = delete(User).where(User.id == principal_id)
    result = await session.execute(stmt)
    return result.rowcount
```

### Composing Erasure Plans

```python
from svc_infra.data.erasure import ErasureStep, ErasurePlan

user_erasure_plan = ErasurePlan(steps=[
    # Order matters! Delete dependencies first
    ErasureStep(name="comments", run=erase_user_comments),
    ErasureStep(name="orders", run=erase_user_orders),  # Anonymize, not delete
    ErasureStep(name="profile", run=erase_user_profile),
    ErasureStep(name="account", run=erase_user_account),
])
```

### Executing Erasure

```python
from svc_infra.data.erasure import run_erasure

async def handle_deletion_request(user_id: str):
    """Process GDPR Article 17 deletion request."""
    async with get_session() as session:
        # Run erasure with audit callback
        affected = await run_erasure(
            session,
            principal_id=user_id,
            plan=user_erasure_plan,
            on_audit=log_erasure_event,
        )
        await session.commit()

        logger.info(f"Erased data for user {user_id}: {affected} rows affected")
        return affected

def log_erasure_event(event: str, context: dict):
    """Audit callback for compliance logging."""
    audit_logger.info(
        event,
        extra={
            "principal_id": context["principal_id"],
            "affected_rows": context["affected"],
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
```

### API Endpoint

```python
from fastapi import APIRouter, BackgroundTasks

router = APIRouter()

@router.post("/gdpr/erasure/{user_id}")
async def request_erasure(
    user_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
):
    """GDPR Article 17 - Right to Erasure."""
    # Verify the request (user exists, can be deleted, etc.)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    # Queue erasure as background task
    background_tasks.add_task(handle_deletion_request, user_id)

    return {"status": "accepted", "message": "Erasure request queued"}
```

### Cascade Handling

For complex relationships, order steps carefully:

```python
# Schema:
# User -> Orders -> OrderItems
# User -> Comments
# User -> UserProfile

cascade_erasure_plan = ErasurePlan(steps=[
    # Level 3: Deepest dependencies first
    ErasureStep(name="order_items", run=erase_order_items_by_user),

    # Level 2: Parent of order_items
    ErasureStep(name="orders", run=erase_user_orders),
    ErasureStep(name="comments", run=erase_user_comments),
    ErasureStep(name="profile", run=erase_user_profile),

    # Level 1: Top-level entity last
    ErasureStep(name="account", run=erase_user_account),
])
```

---

## Backup Verification

Ensure backup health with automated verification.

### Basic Verification

```python
from svc_infra.data.backup import verify_backups, BackupHealthReport

# Simple check
report = verify_backups(
    last_success=datetime(2024, 1, 15, 12, 0),  # Last successful backup
    retention_days=1,  # Expect daily backups
)

if report.ok:
    print("Backups are healthy")
else:
    print(f"Backup issue: {report.message}")
```

### Custom Backup Checker

```python
from svc_infra.data.backup import BackupHealthReport

async def check_s3_backups() -> BackupHealthReport:
    """Check backup health in S3."""
    try:
        # List recent backups
        response = s3.list_objects_v2(
            Bucket="my-backups",
            Prefix="db-backups/",
        )

        if not response.get("Contents"):
            return BackupHealthReport(
                ok=False,
                last_success=None,
                retention_days=1,
                message="No backups found",
            )

        # Find most recent
        latest = max(response["Contents"], key=lambda x: x["LastModified"])
        last_success = latest["LastModified"]

        # Check if recent enough
        age_hours = (datetime.utcnow() - last_success).total_seconds() / 3600

        return BackupHealthReport(
            ok=age_hours < 24,
            last_success=last_success,
            retention_days=1,
            message=f"Latest backup: {age_hours:.1f} hours ago",
        )
    except Exception as e:
        return BackupHealthReport(
            ok=False,
            last_success=None,
            retention_days=1,
            message=str(e),
        )
```

### Scheduled Verification Job

```python
from svc_infra.data.backup import make_backup_verification_job

def alert_on_backup_failure(report: BackupHealthReport):
    """Send alert if backups are unhealthy."""
    if not report.ok:
        send_slack_alert(
            channel="#ops-alerts",
            message=f"🚨 Backup verification failed: {report.message}",
        )

backup_job = make_backup_verification_job(
    checker=check_s3_backups,
    on_report=alert_on_backup_failure,
)

# Schedule with jobs runner
queue.schedule(
    name="backup-verify",
    handler=backup_job,
    interval_hours=12,
)
```

---

## Scheduling Integration

Use the jobs system for automated lifecycle management.

### JOBS_SCHEDULE_JSON Configuration

```bash
export JOBS_SCHEDULE_JSON='[
  {"name": "retention-purge", "interval": "6h", "handler": "app.jobs:run_retention"},
  {"name": "backup-verify", "interval": "12h", "handler": "app.jobs:verify_backups_job"},
  {"name": "session-cleanup", "interval": "1h", "handler": "app.jobs:cleanup_sessions"}
]'
```

### Job Handler Implementation

```python
# app/jobs.py
from svc_infra.data.retention import run_retention_purge
from svc_infra.data.backup import verify_backups

async def run_retention():
    """Scheduled retention purge."""
    async with get_session() as session:
        return await run_retention_purge(session, [
            audit_log_retention,
            temp_file_retention,
            old_notification_retention,
        ])

def verify_backups_job():
    """Scheduled backup verification."""
    report = check_backup_status()
    if not report.ok:
        send_ops_alert(f"Backup unhealthy: {report.message}")
    return report

async def cleanup_sessions():
    """Clean up expired sessions."""
    async with get_session() as session:
        # Delete sessions older than 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        stmt = delete(Session).where(Session.expires_at < cutoff)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount
```

---

## Compliance

### GDPR Checklist

- [ ] **Right to Access (Article 15)** — Export user data on request
- [ ] **Right to Erasure (Article 17)** — Delete user data with `ErasurePlan`
- [ ] **Right to Portability (Article 20)** — Export data in machine-readable format
- [ ] **Data Retention** — Define and enforce `RetentionPolicy` for all PII
- [ ] **Audit Trails** — Log all erasure operations with `on_audit` callback
- [ ] **Consent Records** — Maintain proof of consent with timestamps

### Data Subject Request Workflow

```python
@router.post("/gdpr/export/{user_id}")
async def export_user_data(user_id: str):
    """GDPR Article 20 - Data Portability."""
    async with get_session() as session:
        user = await get_user(session, user_id)
        orders = await get_user_orders(session, user_id)
        comments = await get_user_comments(session, user_id)

        return {
            "user": user.to_dict(),
            "orders": [o.to_dict() for o in orders],
            "comments": [c.to_dict() for c in comments],
            "exported_at": datetime.utcnow().isoformat(),
        }

@router.post("/gdpr/rectify/{user_id}")
async def rectify_user_data(
    user_id: str,
    updates: UserUpdate,
):
    """GDPR Article 16 - Right to Rectification."""
    async with get_session() as session:
        user = await get_user(session, user_id)
        for key, value in updates.dict(exclude_unset=True).items():
            setattr(user, key, value)
        await session.commit()

        # Audit log
        audit_logger.info("user_data_rectified", extra={
            "user_id": user_id,
            "fields": list(updates.dict(exclude_unset=True).keys()),
        })

        return user
```

### Audit Logging

```python
import structlog

audit_logger = structlog.get_logger("audit")

def log_data_lifecycle_event(event: str, context: dict):
    """Standard audit log format for compliance."""
    audit_logger.info(
        event,
        principal_id=context.get("principal_id"),
        affected_rows=context.get("affected"),
        action_type=context.get("action_type"),
        timestamp=datetime.utcnow().isoformat(),
        operator=context.get("operator"),  # Admin who initiated
    )
```

---

## Production Recommendations

### Retention Scheduling

| Data Type | Retention | Schedule | Strategy |
|-----------|-----------|----------|----------|
| Audit logs | 90 days | Weekly | Soft delete |
| Temp files | 7 days | Daily | Hard delete |
| Sessions | 30 days | Hourly | Hard delete |
| Analytics | 365 days | Monthly | Archive |

### Erasure Performance

```python
# ✅ Good: Batch delete with limit
async def erase_in_batches(session, user_id: str, batch_size: int = 1000):
    total = 0
    while True:
        stmt = (
            delete(Comment)
            .where(Comment.author_id == user_id)
            .limit(batch_size)
        )
        result = await session.execute(stmt)
        if result.rowcount == 0:
            break
        total += result.rowcount
        await session.commit()  # Commit each batch
    return total

# ❌ Bad: Single large delete (can lock tables)
async def erase_all_at_once(session, user_id: str):
    stmt = delete(Comment).where(Comment.author_id == user_id)
    result = await session.execute(stmt)  # May timeout!
    return result.rowcount
```

### Backup Verification

- Run verification jobs every 12 hours minimum
- Alert immediately on any failure
- Check both backup existence AND restorability
- Maintain backup metadata (size, duration, checksum)

---

## Troubleshooting

### Fixtures Not Running

**Symptom:** Expected data not present after startup.

**Diagnosis:**
```bash
# Check sentinel file
ls -la .fixtures_loaded

# Check logs for fixture execution
grep "fixture" logs/app.log
```

**Solutions:**
1. Delete sentinel file to re-run: `rm .fixtures_loaded`
2. Verify fixture functions are async-compatible
3. Check for exceptions in fixture code
4. Ensure database connection is available during startup

### Retention Not Purging

**Symptom:** Old data not being deleted.

**Diagnosis:**
```python
# Check policy configuration
print(f"Cutoff: {older_than_days} days")
print(f"Model has created_at: {hasattr(model, 'created_at')}")
print(f"Soft delete field: {soft_delete_field}")
```

**Solutions:**
1. Verify `created_at` column exists on model
2. Check `extra_where` conditions aren't too restrictive
3. Confirm job is actually being scheduled
4. Review database permissions for DELETE operations

### Erasure Failing

**Symptom:** GDPR erasure requests fail or incomplete.

**Diagnosis:**
```python
# Test each step individually
for step in erasure_plan.steps:
    try:
        result = await step.run(session, user_id)
        print(f"{step.name}: {result} rows")
    except Exception as e:
        print(f"{step.name}: FAILED - {e}")
```

**Solutions:**
1. Check foreign key constraints — delete in correct order
2. Verify user_id is correct type (string vs UUID)
3. Add missing cascade delete rules
4. Check database transaction isolation level

---

## API Reference

### run_fixtures

```python
async def run_fixtures(
    loaders: Iterable[Callable[[], None | Awaitable[None]]],
    *,
    run_once_file: str | None = None,
) -> None:
    """Run fixture loaders with optional idempotency."""
```

### RetentionPolicy

```python
@dataclass(frozen=True)
class RetentionPolicy:
    name: str                           # Policy identifier
    model: Any                          # SQLAlchemy model
    older_than_days: int                # Age threshold
    soft_delete_field: str | None       # Column for soft delete
    extra_where: Sequence[Any] | None   # Additional filters
    hard_delete: bool                   # If True, DELETE rows
```

### run_retention_purge

```python
async def run_retention_purge(
    session: AsyncSession,
    policies: Iterable[RetentionPolicy],
) -> int:
    """Execute retention policies, return total affected rows."""
```

### ErasurePlan

```python
@dataclass(frozen=True)
class ErasureStep:
    name: str
    run: Callable[[Session, str], Awaitable[int] | int]

@dataclass(frozen=True)
class ErasurePlan:
    steps: Iterable[ErasureStep]
```

### run_erasure

```python
async def run_erasure(
    session: AsyncSession,
    principal_id: str,
    plan: ErasurePlan,
    *,
    on_audit: Callable[[str, dict], None] | None = None,
) -> int:
    """Execute erasure plan with optional audit callback."""
```

### verify_backups

```python
def verify_backups(
    *,
    last_success: datetime | None = None,
    retention_days: int | None = None,
) -> BackupHealthReport:
    """Return backup health report."""

@dataclass(frozen=True)
class BackupHealthReport:
    ok: bool
    last_success: datetime | None
    retention_days: int | None
    message: str
```

### add_data_lifecycle

```python
def add_data_lifecycle(
    app: FastAPI,
    *,
    auto_migrate: bool = True,
    database_url: str | None = None,
    discover_packages: list[str] | None = None,
    with_payments: bool | None = None,
    on_load_fixtures: Callable[[], None] | None = None,
    retention_jobs: Iterable[Callable] | None = None,
    erasure_job: Callable[[str], None] | None = None,
) -> None:
    """Wire data lifecycle conveniences on app startup."""
```

---

## See Also

- [Database Guide](database.md) — SQL session and repository patterns
- [Jobs Guide](jobs.md) — Background job scheduling
- [Auth Guide](auth.md) — User management
- [CLI Reference](cli.md) — Database migration commands
