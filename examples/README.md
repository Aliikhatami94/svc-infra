# svc-infra Template

A comprehensive example demonstrating **ALL** svc-infra features for building production-ready FastAPI services.

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

### Option 1: Run in Examples Directory

```bash
# 1. Navigate to examples directory
cd examples

# 2. Install dependencies
poetry install

# 3. Copy environment template
cp .env.example .env

# 4. Create database tables
poetry run python create_tables.py

# 5. Start the server
./run.sh

cd svc-infra/examples

# Install dependencies

# 2. Install dependenciesmake install

poetry install

```

Server starts at **http://localhost:8001**

- OpenAPI docs: http://localhost:8001/docs
- Health check: http://localhost:8001/v1/status
- Metrics: http://localhost:8001/metrics

### Option 2: Copy as Standalone Project

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

### 5. Feature Toggles

Enable/disable features via `.env`:

```bash
SQL_URL=sqlite+aiosqlite:///./svc_infra_template.db  # Enable database
# REDIS_URL=redis://localhost:6379/0                 # Enable cache
METRICS_ENABLED=true                                  # Enable metrics

RATE_LIMIT_ENABLED=true                              # Enable rate limiting# Or manually with uvicorn

```poetry run uvicorn --app-dir src svc_infra_template.main:app --reload --host 0.0.0.0 --port 8000

```

## 📁 Project Structure

The API will be available at:

```- API: http://localhost:8000 (configurable via `API_PORT` in `.env`)

examples/- Docs: http://localhost:8000/docs

├── src/svc_infra_template/- OpenAPI: http://localhost:8000/openapi.json

│   ├── main.py           # 🎯 400+ lines of educational comments!

│   ├── settings.py       # Type-safe configuration### Available Endpoints

│   ├── db/

│   │   ├── base.py       # SQLAlchemy base, mixins- `GET /v1/ping` - Health check

│   │   ├── session.py    # Session management- `GET /v1/status` - Service status

│   │   └── models.py     # Example models- `GET /ping` - Root health check (added by svc-infra)

│   └── api/v1/- `GET /metrics` - Prometheus metrics (when observability enabled)

│       └── routes.py     # v1 endpoints

```

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
3. **Read [Database Guide](docs/DATABASE.md)** - Database setup, migrations, auto-CRUD
4. **Check [CLI Reference](docs/CLI.md)** - svc-infra command-line tools
5. **Explore `db/models.py`** - SQLAlchemy 2.0 async patterns with ModelBase
6. **Review `api/v1/routes.py`** - Custom endpoint examples
7. **Toggle features** - Change `.env` and see how the API adapts

## 🛠️ Available Endpoints

Visit `/docs` for interactive documentation, or:

**Core:**
- `GET /` - Service info
- `GET /v1/status` - System status
- `GET /v1/features` - Feature flags
- `GET /v1/stats/summary` - Statistics

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
