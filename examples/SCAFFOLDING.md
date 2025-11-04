# Model Scaffolding Guide

This guide explains how to use the scaffolding scripts to generate SQLAlchemy models and Pydantic schemas for your svc-infra-template project.

## 🎯 Key Concept: Learning by Doing

The scaffolding scripts (`scaffold_models.py` and `quick_setup.py`) are **educational reference implementations**. They demonstrate how to:

1. **Call svc-infra CLI commands directly** (not Python module imports)
2. **Automate common setup tasks** (model generation + migrations)
3. **Provide clear output** showing what's happening

You can use these scripts as-is, or **copy the CLI commands** they show and run them manually. They're designed to teach you the CLI while being immediately useful.

## 🚀 Quick Start

### Automated Setup (Easiest)

```bash
poetry run python scripts/quick_setup.py
```

This single command:
1. ✅ Generates User, Project, and Task models + schemas
2. ✅ Initializes Alembic
3. ✅ Creates migration
4. ✅ Applies migration to database
5. ✅ Shows next steps

**✨ Safe by default:** Won't overwrite existing models unless you use `--overwrite`

### Manual Scaffolding

If you want more control or only need specific models:

```bash
# Generate all models (no migrations)
poetry run python scripts/scaffold_models.py

# Only User model (for authentication)
poetry run python scripts/scaffold_models.py --user-only

# Only business models (Project/Task)
poetry run python scripts/scaffold_models.py --entities-only

# Overwrite existing files (USE WITH CAUTION)
poetry run python scripts/scaffold_models.py --overwrite
```

**🛡️ Duplicate Prevention:** Scripts automatically detect existing models and skip them to prevent accidental overwrites. Use `--overwrite` flag only if you're certain you want to replace existing code.

## 📁 What Gets Generated

### User Model (Authentication)

**Files:**
- `src/svc_infra_template/models/user.py`
- `src/svc_infra_template/schemas/user.py`

**Includes:**
- Inherits from `SQLAlchemyBaseUserTableUUID` (fastapi-users)
- Email, hashed_password, is_active, is_superuser, is_verified
- tenant_id (for multi-tenancy support)
- Standard audit fields (created_at, updated_at)

**Usage:**
```python
from svc_infra_template.models.user import User
from svc_infra_template.schemas.user import UserRead, UserCreate, UserUpdate

# In main.py
add_auth_users(
    app,
    user_model=User,
    schema_read=UserRead,
    schema_create=UserCreate,
    schema_update=UserUpdate,
)
```

### Project Model (Business Entity)

**Files:**
- `src/svc_infra_template/models/project.py`
- `src/svc_infra_template/schemas/project.py`

**Includes:**
- Integer primary key
- tenant_id (for multi-tenancy)
- deleted_at (soft delete support)
- is_active flag
- Audit fields (created_at, updated_at)

**Customize:**
```python
# Add custom fields in models/project.py
class Project(ModelBase):
    __tablename__ = "projects"

    # Scaffolded fields...

    # Add your custom fields:
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_email: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
```

### Task Model (Business Entity)

**Files:**
- `src/svc_infra_template/models/task.py`
- `src/svc_infra_template/schemas/task.py`

**Includes:**
- Integer primary key
- tenant_id (for multi-tenancy)
- is_active flag
- Audit fields (created_at, updated_at)
- No soft delete (tasks are hard-deleted)

## 🔧 Command Reference

### quick_setup.py

**Purpose:** All-in-one setup script that generates models and runs migrations.

```bash
# Full setup
poetry run python quick_setup.py

# Options
--skip-migrations    # Generate models but skip migrations
--overwrite          # Overwrite existing model files
```

**Exit codes:**
- `0` - Success
- `1` - Failure (check output for details)

### scaffold_models.py

**Purpose:** Generate models without running migrations (more granular control).

```bash
# Generate all models
poetry run python scaffold_models.py

# Options
--user-only         # Only generate User model
--entities-only     # Only generate Project/Task models
--overwrite         # Overwrite existing files
```

## 🎯 Workflows

### Workflow 1: New Project Setup

```bash
# 1. Scaffold everything
poetry run python quick_setup.py

# 2. Customize models
# Edit src/svc_infra_template/models/*.py

# 3. Create new migration (if you made changes)
poetry run python -m svc_infra.db revision -m "customize models" --project-root .

# 4. Apply migration
poetry run python -m svc_infra.db upgrade head --project-root .

# 5. Enable features in .env
echo "AUTH_ENABLED=true" >> .env
echo "TENANCY_ENABLED=true" >> .env

# 6. Update main.py
# Uncomment add_auth_users() section
# Import your User model and schemas

# 7. Start server
make run
```

### Workflow 2: Add Auth to Existing Project

```bash
# 1. Generate only User model
poetry run python scaffold_models.py --user-only

# 2. Review and customize User model
# Edit src/svc_infra_template/models/user.py

# 3. Create migration
poetry run python -m svc_infra.db revision -m "add user model" --project-root .

# 4. Apply migration
poetry run python -m svc_infra.db upgrade head --project-root .

# 5. Update main.py with auth integration
# See comments in main.py for complete example

# 6. Enable auth
echo "AUTH_ENABLED=true" >> .env
```

### Workflow 3: Add New Entity Model

```bash
# Use svc-infra CLI directly for custom entities
poetry run python -m svc_infra.cli sql scaffold \
  --kind entity \
  --entity-name Product \
  --table-name products \
  --models-dir src/svc_infra_template/models \
  --schemas-dir src/svc_infra_template/schemas \
  --models-filename product.py \
  --schemas-filename product.py

# Then run migration
poetry run python -m svc_infra.db revision -m "add product model" --project-root .
poetry run python -m svc_infra.db upgrade head --project-root .
```

## 🔍 Actual CLI Commands Used

The scaffold scripts call these **actual CLI commands** (you can run these manually too):

```bash
# Scaffold auth model (User)
svc-infra sql scaffold \
  --kind auth \
  --entity-name User \
  --table-name users \
  --models-dir src/svc_infra_template/models \
  --schemas-dir src/svc_infra_template/schemas \
  --models-filename user.py \
  --schemas-filename user.py

# Scaffold entity model (Project)
svc-infra sql scaffold \
  --kind entity \
  --entity-name Project \
  --table-name projects \
  --models-dir src/svc_infra_template/models \
  --schemas-dir src/svc_infra_template/schemas \
  --models-filename project.py \
  --schemas-filename project.py \
  --include-tenant \
  --include-soft-delete

# Database commands
svc-infra sql init --project-root .
svc-infra sql revision -m "message" --project-root .
svc-infra sql upgrade head --project-root .
svc-infra sql current --project-root .
svc-infra sql history --project-root .
```

**The scripts just automate calling these commands** - you can copy/paste them and run manually if you prefer!

## 💡 Tips

### Customizing Generated Models

1. **Add fields:**
   ```python
   # In models/user.py
   phone: Mapped[Optional[str]] = mapped_column(String(20))
   avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
   ```

2. **Add relationships:**
   ```python
   # In models/project.py
   tasks: Mapped[list["Task"]] = relationship(back_populates="project")

   # In models/task.py
   project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
   project: Mapped["Project"] = relationship(back_populates="tasks")
   ```

3. **Add indexes:**
   ```python
   email: Mapped[str] = mapped_column(String(255), index=True, unique=True)
   ```

4. **Add validation:**
   ```python
   # In schemas/user.py
   from pydantic import field_validator

   class UserCreate(BaseModel):
       @field_validator('email')
       def validate_email(cls, v):
           if not '@' in v:
               raise ValueError('Invalid email')
           return v.lower()
   ```

### Regenerating Models

If you need to regenerate models after customization:

1. **Backup your customizations:**
   ```bash
   cp src/svc_infra_template/models/user.py user_backup.py
   ```

2. **Regenerate:**
   ```bash
   poetry run python scaffold_models.py --overwrite
   ```

3. **Merge your customizations back**

### Using Custom Table Names

The scaffolder respects environment variables:

```bash
# For auth models
export AUTH_TABLE_NAME=app_users
poetry run python scaffold_models.py --user-only
```

Or pass explicitly:
```bash
poetry run python -m svc_infra.cli sql scaffold \
  --kind auth \
  --table-name app_users \
  ...
```

## 🐛 Troubleshooting

### "Module not found" error

Make sure you're in the examples directory:
```bash
cd examples
poetry run python scaffold_models.py
```

### "Already exists" error

Use `--overwrite` to replace existing files:
```bash
poetry run python scaffold_models.py --overwrite
```

### Migration fails

Check your SQL_URL in .env:
```bash
# SQLite (development)
SQL_URL=sqlite+aiosqlite:///./svc_infra_template.db

# PostgreSQL (production)
SQL_URL=postgresql+asyncpg://user:pass@localhost/dbname
```

### Import errors after scaffolding

Make sure __init__.py files exist:
```bash
ls src/svc_infra_template/models/__init__.py
ls src/svc_infra_template/schemas/__init__.py
```

If missing, create them:
```bash
touch src/svc_infra_template/models/__init__.py
touch src/svc_infra_template/schemas/__init__.py
```

## 📚 Related Documentation

- [Database Guide](docs/DATABASE.md) - Complete database setup
- [CLI Reference](docs/CLI.md) - All svc-infra CLI commands
- [main.py](src/svc_infra_template/main.py) - See auth integration example (commented)
- [.env.example](.env.example) - All configuration options

## 🤝 Contributing

Found an issue with the scaffold scripts? Please open an issue or PR in the svc-infra repository.
