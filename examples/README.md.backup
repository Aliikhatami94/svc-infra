# svc-infra Template

Example service template demonstrating how to use svc-infra utilities to build a production-ready FastAPI service.

## 🚀 Quick Start

This template can be used in two ways:

### Option 1: As a Standalone Project (Recommended)

Copy this template to your own workspace:

```bash
# Copy the template to your workspace
cp -r svc-infra/examples ~/my-projects/my-service

cd ~/my-projects/my-service

# Rename the package (optional)
mv src/svc_infra_template src/my_service
# Update imports in main.py and other files

# Update pyproject.toml dependency:
# Change: svc-infra = { path = "../", develop = true }
# To:     svc-infra = "^0.1.0"

# Install dependencies
make install

# Start the server
make run
```

### Option 2: Run Inside svc-infra Project

If you're working within the svc-infra repo itself:

```bash
# From the svc-infra root
cd examples

# Install dependencies (uses local svc-infra from parent)
poetry install

# Start the server
make run
```

The template uses `svc-infra` as a dependency. When standalone, it fetches from PyPI. When inside the repo, it uses the local development version via `path = "../", develop = true`.

## 📁 Project Structure

```
examples/                        # In svc-infra repo
├── src/
│   └── svc_infra_template/     # Template package (rename to your service)
│       ├── __init__.py
│       ├── main.py             # App entry point (300+ lines of educational comments!)
│       └── api/
│           └── v1/
│               ├── __init__.py  # v1 router
│               └── routes.py    # v1 endpoints
├── pyproject.toml              # Poetry config
├── .env.example                # Environment template
├── run.sh                      # Start script
├── Makefile                    # Common commands
├── README.md                   # This file
└── USAGE.md                    # Detailed usage guide
```

## Setup

```bash
# Install dependencies and create virtual environment
make install

# The .env file will be auto-created from .env.example when you run the app
# Or manually copy it:
cp .env.example .env
```

## Running the Application

```bash
# Start the development server (easiest)
make run

# Or use the run script directly
./run.sh

# Or manually with uvicorn
poetry run uvicorn --app-dir src svc_infra_template.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000 (configurable via `API_PORT` in `.env`)
- Docs: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json

### Available Endpoints

- `GET /v1/ping` - Health check
- `GET /v1/status` - Service status
- `GET /ping` - Root health check (added by svc-infra)
- `GET /metrics` - Prometheus metrics (when observability enabled)

## Extending This Example

The `main.py` file is organized in 4 clear steps for easy customization:

1. **Logging Setup** - Environment-aware log levels and formats
2. **Service Configuration** - Name, version, contact, license, API versions
3. **Add Features** - Uncomment what you need: DB, auth, payments, observability, etc.
4. **Custom Extensions** - Add your own middleware, startup logic, etc.

Each step has detailed comments and examples. Teams can:
- Enable/disable features independently
- Customize per environment
- Add team-specific middleware
- Control CORS, versioning, and routing

## Development

```bash
# See all available commands
make help

# Clean cache files
make clean

# Update dependencies
make update

# Open Poetry shell
make shell
```

## Features & Design Philosophy

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
- Commented examples for all available features
