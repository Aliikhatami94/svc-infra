# Database Guide

Production-ready database infrastructure with SQLAlchemy async, MongoDB, migrations, and connection management.

## Overview

svc-infra provides comprehensive database support with:

- **SQL Databases**: PostgreSQL (recommended), MySQL, SQLite, MSSQL, Snowflake, DuckDB
- **NoSQL**: MongoDB via Motor async client
- **Connection Management**: Automatic URL resolution, pooling, SSL defaults
- **Migrations**: Alembic integration with auto-discovery
- **Repository Pattern**: Type-safe CRUD operations with soft-delete support
- **Multi-Tenancy**: Built-in tenant scoping for queries
- **Health Checks**: Database connectivity probes

## Quick Start

### SQL (PostgreSQL)

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.db.sql.add import add_sql_db, setup_sql
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

app = FastAPI()

# Option 1: Just lifecycle management
add_sql_db(app)  # Reads SQL_URL from environment

# Option 2: Full setup with CRUD routes
from svc_infra.db.sql.resource import SqlResource
from myapp.models import User

setup_sql(
    app,
    resources=[
        SqlResource(model=User, prefix="/users", tags=["users"]),
    ],
)

# Use in routes
@app.get("/users/{user_id}")
async def get_user(user_id: str, session: SqlSessionDep):
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

### MongoDB

```python
from fastapi import FastAPI, Depends
from svc_infra.db.nosql.mongo.client import init_mongo, acquire_db, close_mongo
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mongo()  # Reads MONGO_URL and MONGO_DB from env
    yield
    await close_mongo()

app = FastAPI(lifespan=lifespan)

@app.get("/items")
async def list_items():
    db = await acquire_db()
    items = await db.items.find({}).to_list(100)
    return items
```

---

## SQL Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SQL_URL` | — | Full database URL (recommended) |
| `DATABASE_URL` | — | Alternative URL variable (Heroku/Railway compatible) |
| `DB_DIALECT` | `postgresql` | Database dialect (postgresql, mysql, sqlite, mssql) |
| `DB_DRIVER` | auto | Driver (asyncpg, psycopg, aiosqlite, etc.) |
| `DB_HOST` | — | Database hostname or Unix socket path |
| `DB_PORT` | — | Database port |
| `DB_NAME` | — | Database name |
| `DB_USER` | — | Database username |
| `DB_PASSWORD` | — | Database password |
| `DB_PARAMS` | — | Query params (e.g., `sslmode=require&connect_timeout=5`) |
| `DB_PASSWORD_FILE` | — | Path to file containing password (Docker secrets) |
| `SQL_URL_FILE` | — | Path to file containing full URL |
| `DB_CONNECT_TIMEOUT` | `10` | Connection timeout in seconds |
| `DB_STATEMENT_TIMEOUT_MS` | — | Per-transaction statement timeout (PostgreSQL) |
| `DB_SSLMODE_DEFAULT` | `require` | Default SSL mode for PostgreSQL |
| `DB_FORCE_DRIVER` | — | Force specific driver (psycopg, psycopg2) |

### URL Resolution Order

svc-infra resolves database URLs in this order:

1. **Direct environment variables**: `SQL_URL`, `DB_URL`, `DATABASE_URL`, `DATABASE_URL_PRIVATE`, `PRIVATE_SQL_URL`
2. **File pointers**: `SQL_URL_FILE`, `{VAR}_FILE` suffix
3. **Docker/Kubernetes secrets**: `/run/secrets/database_url`
4. **Composed from parts**: `DB_HOST` + `DB_NAME` + other `DB_*` variables

```python
# Example: Compose URL from parts
# .env
DB_DIALECT=postgresql
DB_DRIVER=asyncpg
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=postgres
DB_PASSWORD=secret
DB_PARAMS=sslmode=disable

# Results in: postgresql+asyncpg://postgres:secret@localhost:5432/myapp?sslmode=disable
```

### Connection Pooling

SQLAlchemy async engines use sensible defaults. Override via URL params or engine configuration:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    database_url,
    pool_size=20,           # Default: 5
    max_overflow=10,        # Default: 10
    pool_timeout=30,        # Default: 30
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True,     # Verify connections before use
)
```

### SSL/TLS Configuration

svc-infra applies secure defaults for production PostgreSQL:

```bash
# PostgreSQL SSL modes (via DB_SSLMODE_DEFAULT or DB_PARAMS)
sslmode=disable     # No SSL (development only!)
sslmode=allow       # Use SSL if available
sslmode=prefer      # Prefer SSL
sslmode=require     # Require SSL (default in svc-infra)
sslmode=verify-ca   # Require SSL + verify CA
sslmode=verify-full # Require SSL + verify CA + hostname
```

For asyncpg, SSL is handled via connect_args:

```python
# Automatic for PostgreSQL URLs when DB_SSLMODE_DEFAULT is set
# or when URL contains sslmode=require
```

---

## Migrations with Alembic

### Initialize Alembic

```bash
# Using CLI
svc-infra sql init

# Or programmatically
from svc_infra.db.sql.core import init_alembic
init_alembic(script_location="migrations")
```

This creates:
- `alembic.ini` - Configuration file
- `migrations/env.py` - Auto-generated with model discovery
- `migrations/versions/` - Migration scripts

### Generate Migrations

```bash
# Auto-generate from model changes
svc-infra sql revision --autogenerate -m "add users table"

# Empty migration for manual edits
svc-infra sql revision -m "seed data"
```

```python
# Programmatic
from svc_infra.db.sql.core import revision

revision(
    message="add users table",
    autogenerate=True,
    ensure_head_before_autogenerate=True,
)
```

### Run Migrations

```bash
# Upgrade to latest
svc-infra sql upgrade head

# Upgrade to specific revision
svc-infra sql upgrade abc123

# Downgrade one step
svc-infra sql downgrade -1

# Downgrade to specific revision
svc-infra sql downgrade abc123
```

```python
# Programmatic
from svc_infra.db.sql.core import upgrade, downgrade

upgrade()              # To head
upgrade("abc123")      # To specific revision
downgrade(steps=1)     # One step back
```

### Migration Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALEMBIC_DISCOVER_PACKAGES` | — | Comma-separated packages to scan for models |
| `ALEMBIC_INCLUDE_SCHEMAS` | — | Additional schemas to include |
| `ALEMBIC_SKIP_DROPS` | `false` | Prevent table drops in autogenerate |

### Model Discovery

svc-infra's env.py automatically discovers models:

```python
# Automatic: imports ModelBase.metadata from svc_infra.db.sql.base
from svc_infra.db.sql.base import ModelBase

class User(ModelBase):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True)

# Models extending ModelBase are auto-discovered
```

### Multi-Database Migrations

```python
# alembic.ini can point to different databases per environment
# Use ALEMBIC_CONFIG env var to switch configurations

# CI/CD example:
# 1. Test migrations against ephemeral DB
# 2. Validate with --sql flag
svc-infra sql upgrade head --sql > migration.sql
```

---

## Session Management

### Dependency Injection

```python
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep

@app.post("/users")
async def create_user(data: UserCreate, session: SqlSessionDep):
    user = User(**data.dict())
    session.add(user)
    # Auto-commits on success, rolls back on exception
    return user
```

### Transaction Boundaries

Sessions auto-commit on successful request, auto-rollback on exception:

```python
@app.post("/transfer")
async def transfer(from_id: str, to_id: str, amount: int, session: SqlSessionDep):
    # Both operations in same transaction
    from_account = await session.get(Account, from_id)
    from_account.balance -= amount

    to_account = await session.get(Account, to_id)
    to_account.balance += amount

    # Commits together or rolls back together
    return {"status": "ok"}
```

### Statement Timeouts

Prevent runaway queries with per-transaction timeouts:

```bash
# PostgreSQL only
DB_STATEMENT_TIMEOUT_MS=30000  # 30 seconds
```

```python
# Applied automatically via SET LOCAL statement_timeout
# Scoped to the current transaction only
```

---

## Repository Pattern

### SqlRepository

Type-safe CRUD with soft-delete support:

```python
from svc_infra.db.sql.repository import SqlRepository

repo = SqlRepository(
    model=User,
    id_attr="id",
    soft_delete=True,
    soft_delete_field="deleted_at",
    immutable_fields={"id", "created_at"},
)

# List with pagination
users = await repo.list(session, limit=10, offset=0, order_by=[User.created_at.desc()])

# Get by ID (respects soft-delete)
user = await repo.get(session, "user-123")

# Create
new_user = await repo.create(session, {"email": "test@example.com"})

# Update (ignores immutable fields)
updated = await repo.update(session, "user-123", {"name": "New Name"})

# Delete (soft or hard based on configuration)
await repo.delete(session, "user-123")

# Search with ILIKE
results = await repo.search(
    session,
    q="john",
    fields=["name", "email"],
    limit=10,
    offset=0,
)
```

### SqlService

Business logic layer with hooks:

```python
from svc_infra.db.sql.service import SqlService

class UserService(SqlService):
    async def pre_create(self, data: dict) -> dict:
        # Hash password, validate email, etc.
        data["password_hash"] = hash_password(data.pop("password"))
        return data

    async def pre_update(self, data: dict) -> dict:
        # Audit logging, validation
        return data

# Usage
service = UserService(repo)
user = await service.create(session, {"email": "...", "password": "..."})
```

### Tenant-Scoped Repositories

Automatic tenant isolation:

```python
from svc_infra.db.sql.tenant import TenantSqlService

# All operations scoped to tenant_id
service = TenantSqlService(
    repo,
    tenant_id="tenant-123",
    tenant_field="tenant_id",
)

# List only returns this tenant's records
users = await service.list(session, limit=10, offset=0)

# Create auto-injects tenant_id
user = await service.create(session, {"email": "..."})
# user.tenant_id == "tenant-123"
```

---

## MongoDB Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB` | — | Database name (required) |
| `MONGO_APPNAME` | `svc-infra` | Application name for monitoring |
| `MONGO_MIN_POOL` | `0` | Minimum pool size |
| `MONGO_MAX_POOL` | `100` | Maximum pool size |
| `MONGO_URL_FILE` | — | Path to file containing URL |

### Client Initialization

```python
from svc_infra.db.nosql.mongo.client import init_mongo, acquire_db, close_mongo

# Initialize with custom settings
from svc_infra.db.nosql.mongo.settings import MongoSettings

settings = MongoSettings(
    url="mongodb://user:pass@cluster.mongodb.net",
    db_name="myapp",
    max_pool_size=50,
)
db = await init_mongo(settings)

# Get database reference
db = await acquire_db()

# Operations
await db.users.insert_one({"email": "test@example.com"})
users = await db.users.find({}).to_list(100)

# Cleanup
await close_mongo()
```

### Health Check

```python
from svc_infra.db.nosql.mongo.client import ping_mongo

is_healthy = await ping_mongo()  # Returns True if connected
```

---

## Health Checks

### SQL Health

```python
from svc_infra.api.fastapi.db.sql.add import add_sql_health

add_sql_health(app, prefix="/_sql/health")
# Exposes GET /_sql/health with connection status
```

### Using HealthRegistry

```python
from svc_infra.health import HealthRegistry, check_database, check_redis

registry = HealthRegistry()
registry.add("database", check_database(os.getenv("SQL_URL")), critical=True)
registry.add("redis", check_redis(os.getenv("REDIS_URL")), critical=False)

# Wait for dependencies at startup
await registry.wait_until_healthy(timeout=60, interval=2)
```

---

## SqlResource for CRUD Routes

Auto-generate REST endpoints:

```python
from svc_infra.db.sql.resource import SqlResource

resources = [
    SqlResource(
        model=User,
        prefix="/users",
        tags=["users"],
        id_attr="id",
        soft_delete=True,
        search_fields=["name", "email"],
        ordering_default="-created_at",
        allowed_order_fields=["created_at", "name", "email"],
        # Tenant scoping
        tenant_field="tenant_id",
        # Custom service
        service_factory=lambda repo: UserService(repo),
    ),
]

setup_sql(app, resources)

# Auto-generates:
# GET    /users         - List with pagination, search, ordering
# POST   /users         - Create
# GET    /users/{id}    - Get by ID
# PATCH  /users/{id}    - Update
# DELETE /users/{id}    - Delete (soft if configured)
```

---

## Production Recommendations

### Connection Limits

```bash
# PostgreSQL: connections = (cores * 2) + spindles
# Rule of thumb: pool_size = 10-20 per worker

# For 4 Gunicorn workers with 10 threads each:
# pool_size = 5, max_overflow = 10 per worker
# Total: 4 * 15 = 60 max connections
```

### Read Replicas

```python
# Use different URLs for read vs write
WRITE_DB_URL = os.getenv("PRIMARY_DB_URL")
READ_DB_URL = os.getenv("REPLICA_DB_URL", WRITE_DB_URL)

# Create separate engines
write_engine = create_async_engine(WRITE_DB_URL)
read_engine = create_async_engine(READ_DB_URL)
```

### Backup Verification

```python
from svc_infra.data.lifecycle import verify_backups

# Check backup health
report = await verify_backups(
    expected_max_age_hours=24,
    backup_path="/backups",
)
if not report.healthy:
    alert_ops_team(report)
```

### Statement Timeout Best Practices

```bash
# API endpoints: 30 seconds
DB_STATEMENT_TIMEOUT_MS=30000

# Background jobs: 5 minutes
# Set per-job via session.execute(text("SET LOCAL statement_timeout = 300000"))
```

---

## Troubleshooting

### Connection Errors

```
sqlalchemy.exc.OperationalError: connection refused
```

**Solutions:**
1. Verify `SQL_URL` is set correctly
2. Check network connectivity to database host
3. Verify database is running: `pg_isready -h localhost -p 5432`
4. Check SSL requirements: try `?sslmode=disable` for local dev

### Slow Queries

```python
# Enable SQLAlchemy logging
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# Set statement timeout to catch runaway queries
DB_STATEMENT_TIMEOUT_MS=30000
```

### Migration Conflicts

```
alembic.util.exc.CommandError: Multiple heads
```

**Solution:**
```bash
svc-infra sql merge heads -m "merge branches"
```

### Pool Exhaustion

```
TimeoutError: QueuePool limit of size X overflow Y reached
```

**Solutions:**
1. Increase `pool_size` and `max_overflow`
2. Ensure sessions are closed (use context managers)
3. Add `pool_pre_ping=True` to detect stale connections
4. Check for connection leaks in long-running tasks

### MongoDB Connection Issues

```
motor.motor_asyncio.AsyncIOMotorClient: Connection refused
```

**Solutions:**
1. Verify `MONGO_URL` format: `mongodb://user:pass@host:27017`
2. Check `MONGO_DB` is set
3. Verify replica set name if using Atlas: `?replicaSet=atlas-...`

---

## See Also

- [Tenancy Guide](tenancy.md) - Multi-tenant data isolation
- [Environment Reference](environment.md) - All database environment variables
- [Data Lifecycle](data-lifecycle.md) - Retention policies and GDPR erasure
- [Jobs](jobs.md) - Background database operations
