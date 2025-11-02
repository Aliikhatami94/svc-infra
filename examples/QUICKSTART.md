# Quick Start Guide

Get the svc-infra-template example running in 5 minutes.

## Prerequisites

- Python 3.11 or higher
- Poetry installed (`pip install poetry`)

## Installation

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
```

Server starts at **http://localhost:8001**

- OpenAPI docs: http://localhost:8001/docs
- Health check: http://localhost:8001/v1/status

## 📝 Key Configuration

```bash
# In .env file:
APP_ENV=local              # Environment: local, dev, prod
API_PORT=8001              # Server port
SQL_URL=sqlite+aiosqlite:////tmp/svc_infra_template.db  # Database URL
# REDIS_URL=redis://localhost:6379/0  # Optional: for caching
METRICS_ENABLED=true       # Enable Prometheus metrics
```

## �️ Database Setup

### Quick Start (Development)

Use the provided `create_tables.py` script:

```bash
poetry run python create_tables.py
```

This creates tables directly using SQLAlchemy (no migrations).

### Production Setup (Migrations)

**Important:** When using migrations inside the svc-infra repository, the auto-discovery may include svc-infra's internal models. For production use, copy the template to a standalone directory:

```bash
# Copy template outside svc-infra repo
cp -r svc-infra/examples ~/my-project
cd ~/my-project

# Update pyproject.toml dependency:
# Change: svc-infra = { path = "../", develop = true }
# To:     svc-infra = "^0.1.0"

# Install and run migrations
poetry install
./db-migrate.sh setup-and-migrate --discover-packages=svc_infra_template.db.models --no-with-payments
```

**Alternative:** Use `create_tables.py` for development (simpler, no migration history).

**See [Database Guide](docs/DATABASE.md)** for complete database documentation.

## 🚀 Testing Features

### Auto-Generated CRUD

The template automatically generates REST endpoints for models:

**Projects:**
```bash
# Create a project
curl -X POST http://localhost:8001/_sql/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project",
    "description": "A test project",
    "owner_email": "user@example.com",
    "is_active": true
  }'

# List projects (with pagination)
curl http://localhost:8001/_sql/projects?page=1&size=10

# Search projects
curl http://localhost:8001/_sql/projects?q=test&fields=name,description

# Get a specific project
curl http://localhost:8001/_sql/projects/1

# Update a project
curl -X PATCH http://localhost:8001/_sql/projects/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name"}'

# Delete a project (soft delete)
curl -X DELETE http://localhost:8001/_sql/projects/1
```

**Tasks:**
```bash
# Create a task
curl -X POST http://localhost:8001/_sql/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Task",
    "description": "A test task",
    "status": "pending",
    "project_id": 1
  }'

# List tasks
curl http://localhost:8001/_sql/tasks
```

### Custom Endpoints

```bash
# System status
curl http://localhost:8001/v1/status

# Feature flags
curl http://localhost:8001/v1/features

# Statistics
curl http://localhost:8001/v1/stats/summary
```

### Metrics

```bash
# Prometheus metrics
curl http://localhost:8001/metrics
```

## 🔑 Key Files

- **`main.py`** - **START HERE** - Complete feature showcase with inline docs
- **`settings.py`** - Type-safe configuration with Pydantic
- **`db/models.py`** - SQLAlchemy models (Project, Task)
- **`db/schemas.py`** - Pydantic schemas for API validation
- **`api/v1/routes.py`** - Custom API endpoints
- **`.env.example`** - All available configuration options
- **`create_tables.py`** - Simple table creation script

## 💡 What's Different

This template uses `setup_service_api` (not `easy_service_app`) to showcase:
- **Explicit setup** - Full control over initialization order
- **Feature toggles** - Enable/disable via environment variables
- **Production patterns** - Observability, rate limiting, idempotency
- **Auto-generated CRUD** - Zero-code REST endpoints via `SqlResource`

Read `main.py` for detailed inline documentation!

## 📚 Documentation

- **[Database Guide](docs/DATABASE.md)** - Database setup, migrations, auto-CRUD
- **[CLI Reference](docs/CLI.md)** - Complete svc-infra CLI documentation
- **[Usage Guide](USAGE.md)** - Detailed feature usage examples

## 🛠️ Development Commands

```bash
# Run server
./run.sh

# Create database tables
poetry run python create_tables.py

# Run migrations (if using Alembic)
poetry run python -m svc_infra.cli sql upgrade head

# Check migration status
poetry run python -m svc_infra.cli sql current

# Create new migration
poetry run python -m svc_infra.cli sql revision \
  --message "add new field" \
  --autogenerate

# Format code
poetry run black . --line-length 100
poetry run isort . --profile black

# Run tests (if added)
poetry run pytest
```
