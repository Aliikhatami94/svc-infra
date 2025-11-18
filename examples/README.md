# svc-infra Template

A comprehensive example demonstrating **ALL** svc-infra features for building production-ready FastAPI services.

## ⚡ Quick Setup

**Get started in 2 commands:**

```bash
cd examples
make setup    # Installs deps, scaffolds models, runs migrations
make run      # Starts the server at http://localhost:8001
```

**✨ Features:**
- 🛡️ Safe: Won't overwrite existing models (use `--overwrite` if needed)
- 📚 Educational: Calls actual `svc-infra` CLI commands so you can learn
- 🎯 Complete: Generates User (auth), Project, and Task models + migrations

📖 **See [`scripts/auth_reference.py`](scripts/auth_reference.py)** - Complete auth integration example  
📚 **See [`SCAFFOLDING.md`](SCAFFOLDING.md)** - Full scaffolding documentation  
🛠️ **See [Make Commands](#-available-make-commands)** - All available commands

## 🎯 What This Template Showcases

This is a **complete, working example** that demonstrates **ALL 18 svc-infra features**:

### Core Infrastructure
✅ **Flexible Service Setup** - Using `setup_service_api` for full control  
✅ **Auto-Generated CRUD** - Zero-code REST endpoints via `SqlResource`  
✅ **Database Integration** - SQLAlchemy 2.0 + async drivers with proper ModelBase usage  
✅ **Environment-Aware Logging** - Auto-configured with the `pick()` helper  
✅ **Type-Safe Configuration** - Pydantic Settings for all environment variables  

### Production Features
✅ **Observability** - Prometheus metrics + OpenTelemetry tracing  
✅ **Security Headers & CORS** - Production-ready defaults with `add_security()`  
✅ **Timeouts & Resource Limits** - Handler timeout, body read timeout, request size limiting  
✅ **Graceful Shutdown** - Track in-flight requests for zero-downtime deploys  
✅ **Rate Limiting** - Protect endpoints from abuse  
✅ **Idempotency** - Prevent duplicate processing with automatic key management  
✅ **Payment Integration** - Stripe/Adyen/Fake adapters  
✅ **Webhooks** - Outbound event notifications with retry logic  
✅ **Billing & Subscriptions** - Usage-based billing with quota enforcement  

### Advanced Features (Configurable)
✅ **Authentication** - Users, OAuth, MFA, API keys (requires model setup)  
✅ **Multi-Tenancy** - Automatic tenant isolation (header/subdomain/path)  
✅ **Data Lifecycle & GDPR** - Retention, archival, erasure policies  
✅ **Background Jobs** - Redis-backed queue with scheduler  
✅ **Admin Operations** - Impersonation with audit logs  

### Operational
✅ **Health Checks** - Kubernetes-style probes (liveness, readiness, startup)  
✅ **Maintenance Mode** - Graceful service degradation  
✅ **API Versioning** - Clean routing structure  
✅ **Lifecycle Management** - Startup/shutdown handlers  
✅ **Documentation** - Auto-generated OpenAPI with version-scoped docs  

## 🚀 Quick Start

### Option 1: Automated Setup with Make (Recommended)

The easiest way to get started:

```bash
cd examples
make setup    # Installs deps, scaffolds models, runs migrations
make run      # Starts the server
```

The `make setup` command will:
- Install dependencies via Poetry
- Create .env from template
- Generate User model for authentication
- Generate Project and Task models for business logic
- Initialize Alembic migrations
- Create and apply migrations
- Provide next steps for enabling features

### Option 2: Manual Script Execution

If you prefer more control:

```bash
# 1. Navigate to examples directory
cd examples

# 2. Install dependencies
poetry install

# 3. Copy environment template
cp .env.example .env

# 4. Run automated setup (generates User, Project, Task models + migrations)
python scripts/quick_setup.py

# 5. Start the server
make run
```

### Option 3: Fully Manual Setup (Step-by-Step)

For complete control over each step:

```bash
# 1. Navigate to examples directory
cd examples

# 2. Install dependencies
make install

# 3. Copy environment template
cp .env.example .env

# 4. Scaffold models (optional - for auth/tenancy/GDPR)
make scaffold

# 5. Initialize and run migrations
poetry run svc-infra sql init
poetry run svc-infra sql revision -m "Initial tables"
poetry run svc-infra sql upgrade head

# 6. Start the server
make run
```

Server starts at **http://localhost:8001**

- OpenAPI docs: http://localhost:8001/docs
- Health check: http://localhost:8001/ping
- Metrics: http://localhost:8001/metrics
- CRUD endpoints: http://localhost:8001/_sql/projects

## 🛠️ Available Make Commands

```bash
make help       # Show all available commands
make install    # Install dependencies with Poetry
make setup      # Complete setup (install + scaffold + migrations) ⭐
make scaffold   # Scaffold models only (no migrations)
make run        # Start the development server
make clean      # Clean up cache files
make shell      # Open a Poetry shell
make update     # Update dependencies
make test-setup # Test duplicate prevention
```

**Most common workflow:**
```bash
make setup   # First time only
make run     # Every time you want to start the server
```

### Option 4: Copy as Standalone Project

Copy this template to your own workspace:

```bash
# Copy the template
cp -r svc-infra/examples ~/my-projects/my-service
cd ~/my-projects/my-service

# Rename the package (optional)
mv src/svc_infra_template src/my_service

# Update imports in main.py and other files
# Update pyproject.toml dependency:
# Change: svc-infra = { path = "../", develop = true }
# To:     svc-infra = "^0.1.0"

# Install and run
poetry install
poetry run python create_tables.py
./run.sh
```

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[Database Guide](docs/DATABASE.md)** - Complete database setup, migrations, auto-CRUD
- **[CLI Reference](docs/CLI.md)** - svc-infra CLI command documentation
- **[Usage Guide](USAGE.md)** - Detailed feature usage examples

## 📖 Key Features

### 1. Auto-Generated CRUD

**Zero-code REST endpoints** generated from SQLAlchemy models:

```python
from svc_infra.api.fastapi.db.sql.add import add_sql_resources
from svc_infra.db.sql.resource import SqlResource

add_sql_resources(app, resources=[
    SqlResource(
        model=Project,
        prefix="/projects",
        tags=["Projects"],
        soft_delete=True,
        search_fields=["name", "owner_email"],
        ordering_default="-created_at",
        read_schema=ProjectRead,
        create_schema=ProjectCreate,
        update_schema=ProjectUpdate,
    ),
])
```

This automatically generates:
- `POST /_sql/projects` - Create
- `GET /_sql/projects` - List with pagination, search, ordering
- `GET /_sql/projects/{id}` - Get by ID
- `PATCH /_sql/projects/{id}` - Update
- `DELETE /_sql/projects/{id}` - Delete (or soft-delete)

See [Database Guide](docs/DATABASE.md) for complete documentation.

### 2. Flexible Setup Pattern

We use `setup_service_api` instead of `easy_service_app` to demonstrate full control:

```python
app = setup_service_api(
    service=ServiceInfo(name="svc-infra-template", ...),
    versions=[APIVersionSpec(tag="v1", routers_package="svc_infra_template.api.v1")],
    public_cors_origins=settings.cors_origins_list,

)
```

### 3. Environment-Aware Configuration

Using the `pick()` helper for clean environment-based settings:

```python
setup_logging(
    level=pick(
        prod=LogLevelOptions.INFO,
        local=LogLevelOptions.DEBUG,
    )
)
```

### 4. Type-Safe Settings

All configuration in `settings.py` using Pydantic:

```python
class Settings(BaseSettings):
    sql_url: Optional[str] = Field(default=None)
    redis_url: Optional[str] = Field(default=None)
    # ... with validation and defaults
```

### 5. Document Management & Storage

**Complete working examples** showing generic file storage and document management:

#### Storage Demo (`/v1/storage/`)
Direct storage backend operations with any provider (S3, local, memory):

```python
from svc_infra.storage import easy_storage, add_storage

# Auto-detect backend (Railway volumes, S3, etc.)
storage = easy_storage()

# Mount storage endpoints
add_storage(app, storage, serve_files=True)
```

**Available endpoints:**
- `POST /v1/storage/upload` - Upload file with metadata
- `GET /v1/storage/download/{key}` - Download file
- `DELETE /v1/storage/delete/{key}` - Delete file
- `GET /v1/storage/exists/{key}` - Check if file exists
- `POST /v1/storage/signed-url` - Generate signed URL
- `GET /v1/storage/list` - List stored files

#### Documents Demo (`/v1/documents/`)
Generic document management built on svc-infra storage:

```python
from svc_infra.documents import add_documents

# Mount document management endpoints
add_documents(app, storage)
```

**Available endpoints:**
- `POST /v1/documents/upload` - Upload document with metadata tagging
- `POST /v1/documents/upload-file` - Upload via multipart form
- `GET /v1/documents/list` - List documents with search/filter
- `GET /v1/documents/{id}` - Get document metadata
- `GET /v1/documents/{id}/download` - Download document content

**Features:**
- Flexible metadata tagging (category, tags, department, project)
- Search by metadata fields
- User isolation and access control
- Checksum validation
- Content type detection
- Multiple storage backends (S3, local, Railway volumes, memory)

**Example usage:**
```python
# Upload with metadata
response = client.post(
    "/v1/documents/upload",
    files={"file": ("report.pdf", pdf_content, "application/pdf")},
    data={
        "category": "report",
        "tags": "q4,annual",
        "department": "finance",
        "project": "budget-2025",
    }
)

# List with filters
response = client.get(
    "/v1/documents/list",
    params={"category": "report", "limit": 10}
)
```

**Extension pattern:**
This demonstrates the generic base layer. For domain-specific features (like OCR for tax forms, AI analysis), see `fin-infra/documents/` which extends this base with financial capabilities.

**Storage configuration:**
```bash
# Auto-detect (Railway, S3, etc.)
# STORAGE_BACKEND=auto

# Or specify explicitly:
STORAGE_BACKEND=local
STORAGE_BASE_PATH=/data/uploads
STORAGE_BASE_URL=http://localhost:8001/files

# Or S3-compatible:
# STORAGE_BACKEND=s3
# STORAGE_S3_BUCKET=my-bucket
# STORAGE_S3_REGION=us-east-1
# STORAGE_S3_ENDPOINT=https://nyc3.digitaloceanspaces.com
```

**Try it:**
```bash
# Upload a document
curl -F "file=@test.pdf" \
     -F "category=contract" \
     -F "tags=legal,2025" \
     http://localhost:8001/v1/documents/upload

# List documents
curl http://localhost:8001/v1/documents/list

# Download document
curl http://localhost:8001/v1/documents/{id}/download -o downloaded.pdf
```

See [`src/svc_infra_template/documents/`](src/svc_infra_template/documents/) and [`src/svc_infra_template/storage/`](src/svc_infra_template/storage/) for implementation details.

### 6. Feature Toggles

Enable/disable features via `.env`:

```bash
SQL_URL=sqlite+aiosqlite:///./svc_infra_template.db  # Enable database
# REDIS_URL=redis://localhost:6379/0                 # Enable cache
METRICS_ENABLED=true                                  # Enable metrics
RATE_LIMIT_ENABLED=true                              # Enable rate limiting
STORAGE_BACKEND=memory                               # Enable storage (auto/local/s3/memory)
```

Or manually with uvicorn:

```bash
poetry run uvicorn --app-dir src svc_infra_template.main:app --reload --host 0.0.0.0 --port 8000
```

## 🌐 Running the Server

The API will be available at:

- **API**: http://localhost:8000 (configurable via `API_PORT` in `.env`)
- **Docs**: http://localhost:8000/docs
- **OpenAPI**: http://localhost:8000/openapi.json

### Available Endpoints

- `GET /v1/ping` - Health check
- `GET /v1/status` - Service status
- `GET /ping` - Root health check (added by svc-infra)
- `GET /metrics` - Prometheus metrics (when observability enabled)
- `POST /v1/documents/upload` - Upload document with metadata
- `GET /v1/documents/list` - List documents
- `GET /v1/storage/list` - List storage files
- `POST /v1/storage/upload` - Direct storage upload

## 📁 Project Structure

```
examples/
├── src/
│   └── svc_infra_template/
│       ├── __init__.py
│       ├── main.py              # 484-line feature showcase with inline docs
│       ├── settings.py          # Type-safe configuration
│       ├── db/
│       │   ├── __init__.py
│       │   ├── base.py          # ModelBase from svc-infra
│       │   ├── models.py        # SQLAlchemy models (Project, Task)
│       │   └── schemas.py       # Pydantic schemas for API
│       ├── documents/           # Document management demo
│       │   ├── __init__.py
│       │   ├── models.py        # Document models with metadata
│       │   ├── storage.py       # CRUD operations using svc-infra
│       │   └── router.py        # FastAPI endpoints
│       ├── storage/             # Direct storage operations demo
│       │   ├── __init__.py
│       │   └── router.py        # Storage backend endpoints
│       └── api/
│           └── v1/
│               ├── __init__.py
│               └── routes.py    # Custom endpoints
├── docs/
│   ├── DATABASE.md              # Database setup & auto-CRUD guide
│   └── CLI.md                   # CLI command reference
├── create_tables.py             # Simple table creation script
├── pyproject.toml               # Dependencies
├── .env.example                 # All configuration options
├── QUICKSTART.md                # 5-minute getting started guide
├── USAGE.md                     # Detailed feature usage
└── README.md                    # This file
```

## 🎓 Learning Path

1. **Read [QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
2. **Study `main.py`** - 484 lines of inline documentation explaining every feature
3. **Try documents demo** - Upload/list/download files at `/v1/documents/`
4. **Explore storage backends** - Test direct storage operations at `/v1/storage/`
5. **Read [Database Guide](docs/DATABASE.md)** - Database setup, migrations, auto-CRUD
6. **Check [CLI Reference](docs/CLI.md)** - svc-infra command-line tools
7. **Explore `db/models.py`** - SQLAlchemy 2.0 async patterns with ModelBase
8. **Review `documents/` and `storage/`** - File management patterns
9. **Review `api/v1/routes.py`** - Custom endpoint examples
10. **Toggle features** - Change `.env` and see how the API adapts

## 🛠️ Available Endpoints

Visit `/docs` for interactive documentation, or:

**Core:**
- `GET /` - Service info
- `GET /v1/status` - System status
- `GET /v1/features` - Feature flags
- `GET /v1/stats/summary` - Statistics

**Documents & Storage:**
- `POST /v1/documents/upload` - Upload document with metadata tagging
- `POST /v1/documents/upload-file` - Upload via multipart form
- `GET /v1/documents/list` - List documents (search, filter, pagination)
- `GET /v1/documents/{id}` - Get document metadata
- `GET /v1/documents/{id}/download` - Download document content
- `POST /v1/storage/upload` - Direct storage upload
- `GET /v1/storage/download/{key}` - Download file
- `DELETE /v1/storage/delete/{key}` - Delete file
- `GET /v1/storage/exists/{key}` - Check file existence
- `POST /v1/storage/signed-url` - Generate signed URL
- `GET /v1/storage/list` - List stored files

**Auto-Generated CRUD:**
- `POST /_sql/projects` - Create project
- `GET /_sql/projects` - List projects (pagination, search, ordering)
- `GET /_sql/projects/{id}` - Get project
- `PATCH /_sql/projects/{id}` - Update project
- `DELETE /_sql/projects/{id}` - Delete project (soft-delete)
- `POST /_sql/tasks` - Create task
- `GET /_sql/tasks` - List tasks

**Health & Monitoring:**
- `GET /_health/live` - Liveness probe
- `GET /_health/ready` - Readiness probe
- `GET /_health/db` - Database health
- `GET /metrics` - Prometheus metrics

## Extending This Example

The `main.py` file is organized in 4 clear steps for easy customization:

1. **Logging Setup** - Environment-aware log levels and formats
2. **Service Configuration** - Name, version, contact, license, API versions
3. **Add Features** - Toggle via environment: DB, auth, payments, observability, etc.
4. **Custom Extensions** - Add your own middleware, startup logic, etc.

Each step has detailed comments and examples. Teams can:
- Enable/disable features independently
- Customize per environment
- Add team-specific middleware
- Control CORS, versioning, and routing

## �️ Model Scaffolding Scripts

We provide two scripts to automate model generation using svc-infra CLI:

### `quick_setup.py` - All-in-One Setup (Recommended)

Generates models AND runs migrations automatically:

```bash
# Full automated setup
poetry run python quick_setup.py

# Only scaffold models (skip migrations)
poetry run python quick_setup.py --skip-migrations

# Overwrite existing model files
poetry run python quick_setup.py --overwrite
```

**What it does:**
1. ✅ Generates User model (for authentication)
2. ✅ Generates Project and Task models (business logic)
3. ✅ Initializes Alembic migrations
4. ✅ Creates migration file
5. ✅ Applies migration to database
6. ✅ Provides next steps for enabling features

### `scaffold_models.py` - Granular Control

Generate models without running migrations:

```bash
# Generate all models
poetry run python scaffold_models.py

# Only User model (authentication)
poetry run python scaffold_models.py --user-only

# Only business entity models
poetry run python scaffold_models.py --entities-only

# Overwrite existing files
poetry run python scaffold_models.py --overwrite
```

**What it generates:**

1. **User Model** (`models/user.py` + `schemas/user.py`)
   - Inherits from fastapi-users base
   - Includes: email, hashed_password, is_active, is_superuser, is_verified
   - Tenant support for multi-tenancy
   - Soft delete support

2. **Project Model** (`models/project.py` + `schemas/project.py`)
   - Tenant-aware
   - Soft delete support
   - Audit fields (created_at, updated_at)

3. **Task Model** (`models/task.py` + `schemas/task.py`)
   - Tenant-aware
   - Standard timestamps

**After scaffolding**, you can:
- Customize models (add fields, relationships)
- Run migrations manually
- Enable features in `.env`

## 🔓 Enabling Advanced Features

Three powerful features are **included but disabled by default** because they require additional setup:

### 1. Authentication System

Full auth with registration, login, OAuth, MFA, API keys.

**Quick Setup:**
```bash
# Option 1: Automated (recommended)
poetry run python quick_setup.py
# Then uncomment auth section in main.py and set AUTH_ENABLED=true

# Option 2: Manual
poetry run python scaffold_models.py --user-only
poetry run python -m svc_infra.db init --project-root .
poetry run python -m svc_infra.db revision -m "add auth tables" --project-root .
poetry run python -m svc_infra.db upgrade head --project-root .
# Edit main.py to import User model and schemas
# Set AUTH_ENABLED=true in .env
```

**Will Add Routes:**
- `POST /auth/register` - User registration
- `POST /auth/login` - Login with credentials
- `GET /users/me` - Get current user
- `POST /users/verify` - Email verification
- `POST /users/forgot-password` - Password reset
- OAuth endpoints for Google/GitHub
- MFA/TOTP endpoints
- API key management
- Session management
- Session management

**Reference:** See `tests/acceptance/app.py` for a minimal auth implementation example.

### 2. Multi-Tenancy

Automatic tenant isolation for SaaS applications.

**Setup Steps:**
```bash
# 1. Enable in .env
TENANCY_ENABLED=true
TENANCY_HEADER_NAME=X-Tenant-ID

# 2. Restart server
make run

# 3. Send X-Tenant-ID header with requests
curl -H "X-Tenant-ID: tenant-123" http://localhost:8001/_sql/projects
```

**Features:**
- Automatic tenant_id filtering on all queries
- Prevents data leakage between tenants
- Supports header/subdomain/path resolution

### 3. Data Lifecycle & GDPR

Compliance features for data retention and erasure.

**Setup Steps:**
```bash
# 1. Enable in .env
GDPR_ENABLED=true
DATA_AUTO_MIGRATE=true

# 2. Restart server
make run
```

**Features:**
- Automatic data retention policies
- Right to erasure (GDPR Article 17)
- Data export (GDPR Article 20)
- Automatic migrations on startup

---

## Development Commands

```bash
# See all available commands
make help

# Install dependencies
make install

# Start server
make run

# Create database tables
poetry run python create_tables.py

# Run migrations
poetry run python -m svc_infra.cli sql upgrade head

# Clean cache files
make clean

# Update dependencies
poetry update

# Open Poetry shell
poetry shell
```

## 💡 Design Philosophy

This project demonstrates a **flexible, team-friendly** approach to using svc-infra:

### 🎯 Why This Pattern?

- **Pick What You Need**: Enable only the features your team requires (DB, auth, payments, etc.)
- **Clear Extension Points**: Organized in 4 steps: Logging → Service → Features → Custom
- **Team Autonomy**: Each team can customize service metadata, environment behavior, and feature set
- **Production-Ready**: Explicit configuration makes behavior predictable and debuggable
- **Gradual Adoption**: Start simple, add features as you grow

### ✅ Current Setup

- Explicit FastAPI setup with `setup_service_api`
- Environment-aware logging with `setup_logging` + `pick()`
- Versioned API routes (v1) with `APIVersionSpec`
- Rich OpenAPI docs with contact and license info
- Auto-generated CRUD via `SqlResource`
- Database models using svc-infra's `ModelBase`

## 🔧 Customization

### Copy for Your Project

```bash
# Copy template
cp -r svc-infra/examples ~/my-service
cd ~/my-service

# Rename package
mv src/svc_infra_template src/my_service

# Update imports in:
# - main.py
# - settings.py  
# - api/v1/__init__.py

# Update pyproject.toml dependency:
# svc-infra = "^0.1.0"  # Use published version
```

### Add Your Routes

```python
# In api/v1/routes.py
@router.get("/my-endpoint")
async def my_endpoint():
    return {"message": "Hello"}
```

### Add Your Models

```python
# In db/models.py
from svc_infra.db.sql.base import ModelBase as Base

class MyModel(Base, TimestampMixin):
    __tablename__ = "my_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
```

Then create tables (simple) or migrations (production):

**Simple (Development):**
```bash
# Add model to create_tables.py imports
poetry run python create_tables.py
```

**Production (Migrations):**
```bash
poetry run python -m svc_infra.cli sql revision \
  --message "Add MyModel" \
  --autogenerate \
  --project-root .
poetry run python -m svc_infra.cli sql upgrade head --project-root .
```

See [Database Guide](docs/DATABASE.md) for complete details.

---

**🎉 You have a complete, production-ready service template with all svc-infra features!**

For questions, check the inline comments in `main.py` or read the documentation in `docs/`.
