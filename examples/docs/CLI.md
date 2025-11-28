# CLI Command Reference

Complete reference for svc-infra command-line tools.

## Installation & Access

```bash
# Via module (always works)
python -m svc_infra.cli --help

# If installed globally
svc-infra --help
```

---

## SQL Commands

### setup-and-migrate

Initialize Alembic configuration and run migrations in one step.

```bash
python -m svc_infra.cli sql setup-and-migrate [OPTIONS]
```

**Options:**

- `--database-url TEXT` - Database URL (overrides SQL_URL env var)
- `--project-root PATH` - Project root directory (default: `..`)
- `--discover-packages TEXT` - Comma-separated packages to discover models from
- `--no-with-payments` - Skip including payment models
- `--skip-drops` - Don't auto-generate DROP statements in migrations

**Examples:**

```bash
# Basic setup with auto-detection
python -m svc_infra.cli sql setup-and-migrate

# From project root (not subdirectory)
python -m svc_infra.cli sql setup-and-migrate --project-root .

# Only include specific packages
python -m svc_infra.cli sql setup-and-migrate \
  --discover-packages=app.models,app.auth.models

# For apps without payments
python -m svc_infra.cli sql setup-and-migrate --no-with-payments

# Override database URL
python -m svc_infra.cli sql setup-and-migrate \
  --database-url "postgresql+asyncpg://localhost/testdb"
```

### init

Initialize Alembic configuration only (doesn't run migrations).

```bash
python -m svc_infra.cli sql init [OPTIONS]
```

**Options:**

- `--database-url TEXT` - Database URL
- `--project-root PATH` - Project root directory
- `--discover-packages TEXT` - Packages to discover models from
- `--no-with-payments` - Skip payment models

**Example:**

```bash
python -m svc_infra.cli sql init --project-root .
```

### current

Show current migration revision.

```bash
python -m svc_infra.cli sql current [OPTIONS]
```

**Options:**

- `--database-url TEXT` - Database URL
- `--project-root PATH` - Project root directory

**Example:**

```bash
python -m svc_infra.cli sql current
# Output: abc123def456 (head)
```

### history

Show migration history.

```bash
python -m svc_infra.cli sql history [OPTIONS]
```

**Options:**

- `--database-url TEXT` - Database URL
- `--project-root PATH` - Project root directory
- `--verbose` - Show detailed information

**Example:**

```bash
python -m svc_infra.cli sql history --verbose
# Output:
# abc123 -> def456 (head), add user table
# (empty) -> abc123, initial schema
```

### revision

Create a new migration revision.

```bash
python -m svc_infra.cli sql revision [OPTIONS]
```

**Options:**

- `--message TEXT` - Migration message (required)
- `--autogenerate` - Auto-detect model changes
- `--database-url TEXT` - Database URL
- `--project-root PATH` - Project root directory

**Examples:**

```bash
# Manual migration (empty template)
python -m svc_infra.cli sql revision --message "add custom index"

# Auto-generated from model changes
python -m svc_infra.cli sql revision \
  --message "add email field to user" \
  --autogenerate
```

### upgrade

Run migrations forward.

```bash
python -m svc_infra.cli sql upgrade [REVISION] [OPTIONS]
```

**Options:**

- `--database-url TEXT` - Database URL
- `--project-root PATH` - Project root directory

**Examples:**

```bash
# Upgrade to latest
python -m svc_infra.cli sql upgrade head

# Upgrade to specific revision
python -m svc_infra.cli sql upgrade abc123

# Upgrade one step
python -m svc_infra.cli sql upgrade +1
```

### downgrade

Roll back migrations.

```bash
python -m svc_infra.cli sql downgrade [REVISION] [OPTIONS]
```

**Options:**

- `--database-url TEXT` - Database URL
- `--project-root PATH` - Project root directory

**Examples:**

```bash
# Downgrade one step
python -m svc_infra.cli sql downgrade -1

# Downgrade to specific revision
python -m svc_infra.cli sql downgrade abc123

# Downgrade to beginning
python -m svc_infra.cli sql downgrade base
```

### seed

Seed database with initial data.

```bash
python -m svc_infra.cli sql seed SEED_FUNCTION [OPTIONS]
```

**Options:**

- `--database-url TEXT` - Database URL
- `--project-root PATH` - Project root directory

**Example:**

```bash
# Seed function: async def seed_initial_data(session: AsyncSession) -> None
python -m svc_infra.cli sql seed app.db.seeds:seed_initial_data
```

**Seed Function Example:**

```python
# app/db/seeds.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Role

async def seed_initial_data(session: AsyncSession) -> None:
    """Seed initial roles and admin user."""
    # Check if already seeded
    result = await session.execute(select(Role).limit(1))
    if result.scalar_one_or_none():
        print("Database already seeded, skipping")
        return

    # Create roles
    admin_role = Role(name="admin")
    user_role = Role(name="user")
    session.add_all([admin_role, user_role])

    # Create admin user
    admin_user = User(
        email="admin@example.com",
        username="admin",
        role=admin_role,
    )
    session.add(admin_user)

    await session.commit()
    print("✅ Database seeded successfully")
```

### scaffold

Generate both models and schemas files (combined).

```bash
python -m svc_infra.cli sql scaffold [OPTIONS]
```

**Options:**

- `--dest-dir PATH` - Destination directory (required)
- `--kind TEXT` - Scaffold kind: `entity` or `auth` (required)
- `--entity-name TEXT` - Entity name (e.g., "Product", "User")
- `--table-name TEXT` - Table name (e.g., "products", "users")
- `--models-dir PATH` - Models directory (default: same as dest-dir)
- `--schemas-dir PATH` - Schemas directory (default: same as dest-dir)
- `--include-tenant` - Add tenant_id field
- `--include-soft-delete` - Add deleted_at field (entity only)

**Examples:**

```bash
# Scaffold entity with models and schemas together
python -m svc_infra.cli sql scaffold \
  --dest-dir=src/app/db \
  --kind=entity \
  --entity-name=Product \
  --table-name=products \
  --include-tenant \
  --include-soft-delete

# Scaffold entity with separate directories
python -m svc_infra.cli sql scaffold \
  --kind=entity \
  --entity-name=Project \
  --table-name=projects \
  --models-dir=src/app/models \
  --schemas-dir=src/app/schemas

# Scaffold auth (user models)
python -m svc_infra.cli sql scaffold \
  --dest-dir=src/app/auth \
  --kind=auth \
  --entity-name=User
```

**Generated Files:**

- `models.py` - SQLAlchemy models with ModelBase
- `schemas.py` - Pydantic schemas (Base, Read, Create, Update)

### scaffold-models

Generate only models file (no schemas).

```bash
python -m svc_infra.cli sql scaffold-models [OPTIONS]
```

**Options:**

- `--dest-dir PATH` - Destination directory (required)
- `--kind TEXT` - Scaffold kind: `entity` or `auth` (required)
- `--entity-name TEXT` - Entity name (e.g., "Product")
- `--table-name TEXT` - Table name (e.g., "products")
- `--include-tenant` - Add tenant_id field
- `--include-soft-delete` - Add deleted_at field (entity only)

**Examples:**

```bash
# Scaffold only models for entity
python -m svc_infra.cli sql scaffold-models \
  --dest-dir=src/app/models \
  --kind=entity \
  --entity-name=Product \
  --table-name=products

# Scaffold only auth models
python -m svc_infra.cli sql scaffold-models \
  --dest-dir=src/app/auth \
  --kind=auth \
  --entity-name=User
```

**Generated Files:**

- `models.py` - SQLAlchemy models only

### scaffold-schemas

Generate only schemas file (no models).

```bash
python -m svc_infra.cli sql scaffold-schemas [OPTIONS]
```

**Options:**

- `--dest-dir PATH` - Destination directory (required)
- `--kind TEXT` - Scaffold kind: `entity` or `auth` (required)
- `--entity-name TEXT` - Entity name (e.g., "Product")
- `--include-tenant` - Add tenant_id field

**Examples:**

```bash
# Scaffold only schemas for entity
python -m svc_infra.cli sql scaffold-schemas \
  --dest-dir=src/app/schemas \
  --kind=entity \
  --entity-name=Product

# Scaffold only auth schemas
python -m svc_infra.cli sql scaffold-schemas \
  --dest-dir=src/app/schemas \
  --kind=auth \
  --entity-name=User
```

**Generated Files:**

- `schemas.py` - Pydantic schemas only

**📘 For detailed scaffold documentation, see [SCAFFOLD.md](SCAFFOLD.md)**

---

## Observability Commands

### obs-up

Start local observability stack (Prometheus + Grafana).

```bash
svc-infra obs-up [OPTIONS]
```

**Options:**

- `--mode TEXT` - Mode: `local` or `cloud` (default: from .env)

**Behavior:**

- Reads `.env` file in current directory
- Mode `local`: Starts docker-compose with local Grafana + Prometheus
- Mode `cloud`: Starts Grafana Agent configured for Grafana Cloud

**Environment Variables (for cloud mode):**

```bash
GRAFANA_CLOUD_INSTANCE_ID=123456
GRAFANA_CLOUD_API_KEY=glc_xxx
GRAFANA_CLOUD_PROMETHEUS_ENDPOINT=https://prometheus-xxx.grafana.net/api/prom/push
```

**Example:**

```bash
# Start with mode from .env
svc-infra obs-up

# Force local mode
svc-infra obs-up --mode=local

# Access dashboards at:
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
```

### obs-down

Stop local observability stack.

```bash
svc-infra obs-down
```

**Example:**

```bash
svc-infra obs-down
# Stops and removes containers
```

---

## Environment Variables

The CLI respects these environment variables:

### Database

```bash
# Primary connection URL
SQL_URL=postgresql+asyncpg://user:pass@localhost/db

# Or build from parts
DB_DIALECT=postgresql
DB_DRIVER=asyncpg
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=myuser
DB_PASSWORD=secret
DB_PARAMS=pool_size=20&max_overflow=10

# From files (Docker secrets)
SQL_URL_FILE=/run/secrets/database_url
DB_PASSWORD_FILE=/run/secrets/db_password
```

### Alembic

```bash
# Model discovery
ALEMBIC_DISCOVER_PACKAGES=app.models,app.auth.models

# Schema filtering
ALEMBIC_INCLUDE_SCHEMAS=public,tenant_data
ALEMBIC_EXCLUDE_SCHEMAS=information_schema

# Migration behavior
ALEMBIC_SKIP_DROPS=true  # Don't generate DROP statements
```

### Observability

```bash
# Mode selection
OBS_MODE=local  # or 'cloud'

# Grafana Cloud (when mode=cloud)
GRAFANA_CLOUD_INSTANCE_ID=123456
GRAFANA_CLOUD_API_KEY=glc_xxx
GRAFANA_CLOUD_PROMETHEUS_ENDPOINT=https://prometheus-xxx.grafana.net/api/prom/push
GRAFANA_CLOUD_LOKI_ENDPOINT=https://logs-xxx.grafana.net
GRAFANA_CLOUD_TEMPO_ENDPOINT=https://tempo-xxx.grafana.net
```

---

## Common Workflows

### Initial Project Setup

```bash
# 1. Clone/create project
cd my-project

# 2. Install svc-infra
poetry add svc-infra[pg]

# 3. Set database URL
export SQL_URL="postgresql+asyncpg://localhost/myapp"

# 4. Setup migrations and create initial schema
poetry run python -m svc_infra.cli sql setup-and-migrate \
  --project-root . \
  --discover-packages=app.models \
  --no-with-payments
```

### Daily Development

```bash
# 1. Make model changes
# 2. Generate migration
poetry run python -m svc_infra.cli sql revision \
  --message "add email field" \
  --autogenerate

# 3. Review migration
cat migrations/versions/xxx_add_email_field.py

# 4. Apply migration
poetry run python -m svc_infra.cli sql upgrade head

# 5. Run tests
poetry run pytest
```

### Production Deployment

```bash
# In your CI/CD or deployment script:
export SQL_URL="${DATABASE_URL}"  # From environment

# Run migrations
python -m svc_infra.cli sql upgrade head

# Start application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Rolling Back Changes

```bash
# 1. Check current state
python -m svc_infra.cli sql current

# 2. View history
python -m svc_infra.cli sql history

# 3. Rollback one step
python -m svc_infra.cli sql downgrade -1

# 4. Or rollback to specific revision
python -m svc_infra.cli sql downgrade abc123
```

### Seeding Data

```bash
# 1. Create seed function
# app/db/seeds.py: async def seed_initial_data(session: AsyncSession)

# 2. Run seed
python -m svc_infra.cli sql seed app.db.seeds:seed_initial_data

# 3. Verify
psql $SQL_URL -c "SELECT * FROM users;"
```

---

## Troubleshooting

### Command not found

**Problem:** `svc-infra: command not found`

**Solution:** Use module form:

```bash
python -m svc_infra.cli --help
# or
poetry run python -m svc_infra.cli --help
```

### Database connection errors

**Problem:** "could not connect to server"

**Solution:** Check SQL_URL format and server is running:

```bash
# Verify URL format
echo $SQL_URL

# Test connection
psql $SQL_URL -c "SELECT 1;"

# Check async driver is installed
poetry show | grep asyncpg
```

### Models not discovered

**Problem:** Migration doesn't include models

**Solution:**

1. Ensure models inherit from ModelBase:
   ```python
   from svc_infra.db.sql.base import ModelBase
   ```

2. Specify discover packages:
   ```bash
   --discover-packages=app.models
   ```

### Migration conflicts

**Problem:** "multiple heads" or "branch point"

**Solution:**

```bash
# Show heads
python -m svc_infra.cli sql history

# Merge heads
python -m svc_infra.cli sql revision \
  --message "merge heads" \
  --head=abc123 \
  --head=def456
```

---

## Tips & Best Practices

1. **Always use --project-root correctly**
   - From project root: `--project-root .`
   - From subdirectory: `--project-root ..` (default)

2. **Version control migrations**
   - Commit all `migrations/versions/*.py` files
   - Review auto-generated migrations before committing

3. **Use autogenerate carefully**
   - Always review generated migrations
   - Alembic doesn't detect everything (indexes, constraints)
   - Manual editing often needed

4. **Test migrations both ways**
   ```bash
   # Apply
   python -m svc_infra.cli sql upgrade head

   # Rollback
   python -m svc_infra.cli sql downgrade -1

   # Re-apply
   python -m svc_infra.cli sql upgrade head
   ```

5. **Keep migrations atomic**
   - One logical change per migration
   - Easier to review and rollback

6. **Use seed for initial data**
   - Don't hardcode data in migrations
   - Keep seeds idempotent (check before insert)

---

## Further Reading

- [Database Guide](./DATABASE.md) - Complete database setup guide
- [Core CLI Docs](../../docs/cli.md) - Core svc-infra CLI documentation
- [Alembic Docs](https://alembic.sqlalchemy.org/) - Official Alembic documentation
