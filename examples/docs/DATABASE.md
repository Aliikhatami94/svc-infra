# Database Setup Guide

Complete guide to setting up and managing databases with svc-infra.

## Table of Contents

- [Quick Start](#quick-start)
- [Database Models](#database-models)
- [Using svc-infra CLI](#using-svc-infra-cli)
- [Migration Workflows](#migration-workflows)
- [Auto-Generated CRUD](#auto-generated-crud)
- [Connection Configuration](#connection-configuration)

---

## Quick Start

### 1. Define Models with ModelBase

**Important:** Models MUST inherit from `svc_infra.db.sql.base.ModelBase` for migrations to work:

```python
# db/base.py
from svc_infra.db.sql.base import ModelBase as Base

# db/models.py
from svc_infra_template.db.base import Base

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ...
```

### 2. Create Tables

**For Development/Demos** (simplest):

```bash
poetry run python create_tables.py
```

**For Production** (proper migrations):

```bash
# From examples directory
export SQL_URL="sqlite+aiosqlite:////tmp/svc_infra_template.db"

# Setup Alembic and run initial migration
poetry run python -m svc_infra.cli sql setup-and-migrate \
  --discover-packages=svc_infra_template.db.models \
  --no-with-payments
```

### 3. Wire into FastAPI

```python
from svc_infra.api.fastapi.db.sql.add import add_sql_db

# Add database session management
add_sql_db(app, url=settings.sql_url)
```

---

## Database Models

### Using ModelBase

svc-infra's migration system discovers models through `ModelBase`:

```python
# ✅ CORRECT - Will be discovered by migrations
from svc_infra.db.sql.base import ModelBase

class Project(ModelBase):
    __tablename__ = "projects"
    # ...

# ❌ WRONG - Won't be discovered
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Project(Base):  # Won't work with migrations!
    # ...
```

### Scaffold Models with CLI

Generate boilerplate models and schemas:

```bash
# Generate a generic entity model
poetry run python -m svc_infra.cli sql scaffold-models \
  --dest-dir=src/svc_infra_template/db \
  --kind=entity \
  --entity-name=Product \
  --table-name=products \
  --include-tenant \
  --include-soft-delete

# Generate auth models
poetry run python -m svc_infra.cli sql scaffold-models \
  --dest-dir=src/svc_infra_template/auth \
  --kind=auth \
  --entity-name=User
```

### Common Patterns

**Timestamps (auto-managed):**

```python
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

**Soft Delete:**

```python
class SoftDeleteMixin:
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
```

---

## Using svc-infra CLI

### Installation

The CLI is available via:

```bash
# If installed globally
svc-infra --help

# Or via module (works in containers/dev)
python -m svc_infra.cli --help
```

### SQL Commands

**Setup and migrate (end-to-end):**

```bash
# Detects async from URL automatically
python -m svc_infra.cli sql setup-and-migrate \
  --database-url "sqlite+aiosqlite:///./app.db" \
  --discover-packages "app.models" \
  --no-with-payments
```

**Check current migration state:**

```bash
python -m svc_infra.cli sql current
python -m svc_infra.cli sql history
```

**Create new migration:**

```bash
python -m svc_infra.cli sql revision \
  --message "add user table" \
  --autogenerate
```

**Run migrations:**

```bash
# Upgrade to latest
python -m svc_infra.cli sql upgrade head

# Downgrade one step
python -m svc_infra.cli sql downgrade -1

# Upgrade/downgrade to specific revision
python -m svc_infra.cli sql upgrade abc123
```

**Seed data:**

```bash
python -m svc_infra.cli sql seed app.db.seeds:seed_initial_data
```

### Environment Variables

The CLI respects these environment variables:

```bash
# Database URL (primary)
SQL_URL="postgresql+asyncpg://user:pass@localhost/db"

# Or build from parts
DB_DIALECT=postgresql
DB_DRIVER=asyncpg
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=myuser
DB_PASSWORD=secret

# Alembic configuration
ALEMBIC_DISCOVER_PACKAGES=app.models,app.auth.models
ALEMBIC_INCLUDE_SCHEMAS=public,tenant_data
ALEMBIC_SKIP_DROPS=true  # Don't auto-generate DROP statements
```

---

## Migration Workflows

### Initial Setup

```bash
# 1. Ensure models inherit from ModelBase
# 2. Set SQL_URL in environment
export SQL_URL="postgresql+asyncpg://localhost/mydb"

# 3. Initialize Alembic and create initial migration
python -m svc_infra.cli sql setup-and-migrate \
  --discover-packages=app.models

# This creates:
# - migrations/ directory
# - migrations/env.py (configured)
# - migrations/versions/xxx_initial_schema.py
# - Runs the migration
```

### Adding New Models

```bash
# 1. Create your model inheriting from ModelBase
# 2. Generate migration
python -m svc_infra.cli sql revision \
  --message "add product model" \
  --autogenerate

# 3. Review the generated migration in migrations/versions/
# 4. Apply it
python -m svc_infra.cli sql upgrade head
```

### Modifying Models

```bash
# 1. Modify your model
# 2. Generate migration
python -m svc_infra.cli sql revision \
  --message "add email to user" \
  --autogenerate

# 3. Review and edit if needed
# 4. Apply
python -m svc_infra.cli sql upgrade head
```

### Production Deployment

```bash
# In your deployment script/CI:
export SQL_URL="${DATABASE_URL}"  # From secrets

# Run migrations
python -m svc_infra.cli sql upgrade head

# Then start your application
uvicorn app.main:app
```

---

## Auto-Generated CRUD

svc-infra can auto-generate REST CRUD endpoints from your models.

### Setup SqlResource

```python
from svc_infra.api.fastapi.db.sql.add import add_sql_resources
from svc_infra.db.sql.resource import SqlResource
from svc_infra_template.db.models import Project
from svc_infra_template.db.schemas import ProjectCreate, ProjectRead, ProjectUpdate

add_sql_resources(
    app,
    resources=[
        SqlResource(
            model=Project,
            prefix="/projects",
            tags=["Projects"],
            soft_delete=True,  # Enable soft delete
            search_fields=["name", "owner_email"],
            ordering_default="-created_at",
            allowed_order_fields=["id", "name", "created_at"],
            # Pydantic schemas for serialization
            read_schema=ProjectRead,
            create_schema=ProjectCreate,
            update_schema=ProjectUpdate,
        ),
    ],
)
```

This generates these endpoints:

- `POST /_sql/projects` - Create
- `GET /_sql/projects` - List (with pagination, search, ordering)
- `GET /_sql/projects/{id}` - Get by ID
- `PATCH /_sql/projects/{id}` - Update
- `DELETE /_sql/projects/{id}` - Delete (or soft-delete)

### Pydantic Schemas

You need these schemas for serialization:

```python
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    owner_email: str
    is_active: bool = True

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    owner_email: str | None = None
    is_active: bool | None = None

class ProjectRead(BaseModel):
    id: int
    name: str
    description: str | None
    owner_email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
```

### Using Auto-Generated Endpoints

**Create:**

```bash
curl -X POST http://localhost:8001/_sql/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project",
    "description": "A test project",
    "owner_email": "user@example.com"
  }'
```

**List with pagination:**

```bash
curl "http://localhost:8001/_sql/projects?page=1&size=20"
```

**Search:**

```bash
curl "http://localhost:8001/_sql/projects?q=test&fields=name,description"
```

**Order:**

```bash
curl "http://localhost:8001/_sql/projects?order_by=-created_at"
```

**Update:**

```bash
curl -X PATCH http://localhost:8001/_sql/projects/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name"}'
```

**Delete:**

```bash
curl -X DELETE http://localhost:8001/_sql/projects/1
```

---

## Connection Configuration

### SQLite (Development)

```bash
# Synchronous
SQL_URL=sqlite:///./app.db

# Async (recommended)
SQL_URL=sqlite+aiosqlite:///./app.db

# In-memory (testing)
SQL_URL=sqlite+aiosqlite:///:memory:
```

### PostgreSQL (Production)

```bash
# Async (recommended)
SQL_URL=postgresql+asyncpg://user:password@localhost:5432/dbname

# Sync (if needed)
SQL_URL=postgresql+psycopg2://user:password@localhost:5432/dbname

# With connection parameters
SQL_URL=postgresql+asyncpg://user:password@localhost:5432/dbname?pool_size=20&max_overflow=10
```

### MySQL

```bash
# Async
SQL_URL=mysql+aiomysql://user:password@localhost:3306/dbname

# Sync
SQL_URL=mysql+pymysql://user:password@localhost:3306/dbname
```

### Using Environment Parts

Instead of full URL, you can use parts:

```bash
DB_DIALECT=postgresql
DB_DRIVER=asyncpg
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=myuser
DB_PASSWORD=secret
DB_PARAMS=pool_size=20&max_overflow=10
```

### Secrets from Files

```bash
# Read password from file
DB_PASSWORD_FILE=/run/secrets/db_password

# Or entire URL from file
SQL_URL_FILE=/run/secrets/database_url
```

---

## Troubleshooting

### Models not discovered by migrations

**Problem:** Migration doesn't include your models

**Solution:** Ensure models inherit from `ModelBase`:

```python
from svc_infra.db.sql.base import ModelBase as Base

class MyModel(Base):  # ✅ Correct
    ...
```

### Foreign key errors in migrations

**Problem:** `NoReferencedTableError` during migration generation

**Cause:** Trying to generate migrations with svc-infra's internal models (billing, payments) that have foreign keys to tables not in your app.

**Solution:** Use `--discover-packages` to only include your models:

```bash
python -m svc_infra.cli sql setup-and-migrate \
  --discover-packages=your_app.models \
  --no-with-payments
```

### Connection pool exhausted

**Problem:** "QueuePool limit exceeded"

**Solution:** Adjust pool settings in URL or environment:

```bash
SQL_URL=postgresql+asyncpg://...?pool_size=20&max_overflow=10

# Or via parts
DB_PARAMS=pool_size=20&max_overflow=10
```

### Async/sync mismatch

**Problem:** "greenlet_spawn() called in a synchronous context"

**Solution:** Ensure you're using async drivers:
- PostgreSQL: `asyncpg` not `psycopg2`
- MySQL: `aiomysql` not `pymysql`
- SQLite: `aiosqlite` not default

---

## Best Practices

1. **Always use ModelBase** - Required for migration discovery
2. **Use async drivers** - Better performance, required for FastAPI
3. **Version control migrations** - Commit `migrations/versions/` files
4. **Review auto-generated migrations** - Always check before applying
5. **Test migrations** - Run `upgrade` and `downgrade` in dev
6. **Use soft delete for important data** - Set `soft_delete=True` on SqlResource
7. **Index search fields** - Add `index=True` to frequently searched columns
8. **Use Pydantic schemas** - Required for auto-CRUD, validates input

## Further Reading

- [CLI Reference](../../src/svc_infra/docs/cli.md) - Complete CLI documentation
- [Database Guide](../../src/svc_infra/docs/database.md) - Core svc-infra database docs
- [USAGE.md](../USAGE.md) - Full feature usage guide
