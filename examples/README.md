# svc-infra-template - Complete Feature Showcase# svc-infra Template



A comprehensive example demonstrating **ALL** svc-infra utilities for building production-ready FastAPI services.Example service template demonstrating how to use svc-infra utilities to build a production-ready FastAPI service.



## 🎯 What This Template Showcases## 🚀 Quick Start



This is a **complete, working example** that demonstrates:This template can be used in two ways:



✅ **Flexible Service Setup** - Using `setup_service_api` for full control  ### Option 1: As a Standalone Project (Recommended)

✅ **Environment-Aware Logging** - Auto-configured with the `pick()` helper  

✅ **Type-Safe Configuration** - Pydantic Settings for all environment variables  Copy this template to your own workspace:

✅ **Database Integration** - SQLAlchemy 2.0 + Alembic with SQLite (no setup needed!)  

✅ **Observability** - Prometheus metrics + OpenTelemetry tracing  ```bash

✅ **Security Features** - Rate limiting, idempotency, CORS  # Copy the template to your workspace

✅ **Payment Integration** - Stripe/Adyen/Fake adapters  cp -r svc-infra/examples ~/my-projects/my-service

✅ **Webhooks** - Outbound event notifications  

✅ **Health Checks** - Kubernetes-style probes  cd ~/my-projects/my-service

✅ **Custom Middleware** - Request/response processing  

✅ **API Versioning** - Clean routing structure  # Rename the package (optional)

✅ **Lifecycle Management** - Startup/shutdown handlers  mv src/svc_infra_template src/my_service

# Update imports in main.py and other files

## 🚀 Quick Start

# Update pyproject.toml dependency:

```bash# Change: svc-infra = { path = "../", develop = true }

# 1. Navigate to examples directory# To:     svc-infra = "^0.1.0"

cd svc-infra/examples

# Install dependencies

# 2. Install dependenciesmake install

poetry install

# Start the server

# 3. Copy environment filemake run

cp .env.example .env```



# 4. Initialize database (SQLite - no external setup!)### Option 2: Run Inside svc-infra Project

poetry run python -m svc_infra.db init --project-root .

poetry run python -m svc_infra.db revision -m "Initial" --project-root .If you're working within the svc-infra repo itself:

poetry run python -m svc_infra.db upgrade head --project-root .

```bash

# 5. Start the service# From the svc-infra root

make runcd examples



# 6. Visit http://localhost:8001/docs# Install dependencies (uses local svc-infra from parent)

```poetry install



## 📖 Key Features# Start the server

make run

### 1. Flexible Setup Pattern```



We use `setup_service_api` instead of `easy_service_app` to demonstrate full control:The template uses `svc-infra` as a dependency. When standalone, it fetches from PyPI. When inside the repo, it uses the local development version via `path = "../", develop = true`.



```python## 📁 Project Structure

app = setup_service_api(

    service=ServiceInfo(name="svc-infra-template", ...),```

    versions=[APIVersionSpec(tag="v1", routers_package="svc_infra_template.api.v1")],examples/                        # In svc-infra repo

    public_cors_origins=settings.cors_origins_list,├── src/

)│   └── svc_infra_template/     # Template package (rename to your service)

```│       ├── __init__.py

│       ├── main.py             # App entry point (300+ lines of educational comments!)

### 2. Environment-Aware Configuration│       └── api/

│           └── v1/

Using the `pick()` helper for clean environment-based settings:│               ├── __init__.py  # v1 router

│               └── routes.py    # v1 endpoints

```python├── pyproject.toml              # Poetry config

setup_logging(├── .env.example                # Environment template

    level=pick(├── run.sh                      # Start script

        prod=LogLevelOptions.INFO,├── Makefile                    # Common commands

        local=LogLevelOptions.DEBUG,├── README.md                   # This file

    )└── USAGE.md                    # Detailed usage guide

)```

```

## Setup

### 3. Type-Safe Settings

```bash

All configuration in `settings.py` using Pydantic:# Install dependencies and create virtual environment

make install

```python

class Settings(BaseSettings):# The .env file will be auto-created from .env.example when you run the app

    sql_url: Optional[str] = Field(default=None)# Or manually copy it:

    redis_url: Optional[str] = Field(default=None)cp .env.example .env

    # ... with validation and defaults```

```

## Running the Application

### 4. Feature Toggles

```bash

Enable/disable features via `.env`:# Start the development server (easiest)

make run

```bash

SQL_URL=sqlite+aiosqlite:///./svc_infra_template.db  # Enable database# Or use the run script directly

# REDIS_URL=redis://localhost:6379/0                 # Enable cache./run.sh

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

├── pyproject.toml        # Dependencies## Extending This Example

├── .env.example          # All configuration options

└── README.md             # This fileThe `main.py` file is organized in 4 clear steps for easy customization:

```

1. **Logging Setup** - Environment-aware log levels and formats

## 🎓 Learning Path2. **Service Configuration** - Name, version, contact, license, API versions

3. **Add Features** - Uncomment what you need: DB, auth, payments, observability, etc.

1. **Read `main.py`** - Heavily commented to explain every feature4. **Custom Extensions** - Add your own middleware, startup logic, etc.

2. **Study `settings.py`** - See Pydantic Settings patterns

3. **Explore `db/`** - SQLAlchemy 2.0 async patternsEach step has detailed comments and examples. Teams can:

4. **Check `api/v1/routes.py`** - Example endpoints- Enable/disable features independently

5. **Toggle features** - Change `.env` and see API adapt- Customize per environment

- Add team-specific middleware

## 🛠️ Available Endpoints- Control CORS, versioning, and routing



Visit `/docs` for interactive documentation, or:## Development



- `GET /` - Service info```bash

- `GET /v1/status` - Feature flags# See all available commands

- `GET /v1/features` - Full feature discoverymake help

- `GET /_health/live` - Liveness probe

- `GET /_health/ready` - Readiness probe# Clean cache files

- `GET /metrics` - Prometheus metrics (if enabled)make clean



## 📚 Documentation# Update dependencies

make update

- Main app logic: `src/svc_infra_template/main.py`

- Configuration: `src/svc_infra_template/settings.py`# Open Poetry shell

- Database setup: `src/svc_infra_template/db/`make shell

- All options: `.env.example````



## 💡 Use Cases## Features & Design Philosophy



**As a learning tool:**This project demonstrates a **flexible, team-friendly** approach to using svc-infra:

- Study production-ready patterns

- Experiment with features### 🎯 Why This Pattern?

- Understand svc-infra architecture

- **Pick What You Need**: Enable only the features your team requires (DB, auth, payments, etc.)

**As a project template:**- **Clear Extension Points**: Organized in 4 steps: Logging → Service → Features → Custom

- Copy to your workspace- **Team Autonomy**: Each team can customize service metadata, environment behavior, and feature set

- Rename package- **Production-Ready**: Explicit configuration makes behavior predictable and debuggable

- Add your domain logic- **Gradual Adoption**: Start simple, add features as you grow

- Deploy!

### ✅ Current Setup

**As a testing ground:**

- Test svc-infra features locally- Explicit FastAPI setup with `setup_service_api`

- Prototype integrations- Environment-aware logging with `setup_logging` + `pick()`

- Validate configurations- Versioned API routes (v1) with `APIVersionSpec`

- Rich OpenAPI docs with contact and license info

## 🔧 Customization- Commented examples for all available features


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
class MyModel(Base, TimestampMixin):
    __tablename__ = "my_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
```

Then create and run migration:
```bash
poetry run python -m svc_infra.db revision -m "Add MyModel" --project-root .
poetry run python -m svc_infra.db upgrade head --project-root .
```

---

**🎉 You have a complete, production-ready service template with all svc-infra features!**

For questions, check the inline comments in `main.py` - they explain everything!
