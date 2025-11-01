# Quick Start Guide

## What We Built

A minimal FastAPI service using `svc-infra` utilities with:
- ✅ Separate Poetry environment (independent from svc-infra)
- ✅ Auto-configured logging (DEBUG in local, JSON in prod)
- ✅ Auto-configured observability (metrics, tracing)
- ✅ Versioned API routes (v1)
- ✅ Auto-generated OpenAPI documentation
- ✅ Production-ready structure

## Project Structure

```
svc-infra-template/
├── src/
│   └── svc_infra_template/
│       ├── __init__.py
│       ├── main.py              # App entry point
│       └── api/
│           └── v1/
│               ├── __init__.py  # v1 router
│               └── routes.py    # v1 endpoints
├── pyproject.toml               # Poetry config
├── .env.example                 # Environment template
├── run.sh                       # Start script
└── README.md
```

## Quick Start

```bash
# 1. Install dependencies
poetry install

# 2. Start the service
./run.sh

# 3. Test endpoints
curl http://localhost:8000/v1/ping
curl http://localhost:8000/v1/status

# 4. View docs
open http://localhost:8000/docs
```

## Features

This project demonstrates using svc-infra utilities with explicit setup:

- ✅ Explicit FastAPI setup with `setup_service_api`
- ✅ Environment-aware logging with `setup_logging` + `pick()`
- ✅ Versioned API routes with `APIVersionSpec`
- ✅ Rich OpenAPI metadata (contact, license)
- ✅ Ready to extend with more features

### Key Concepts

**1. Explicit Logging Setup**
```python
from svc_infra.app import LogLevelOptions, pick, setup_logging

setup_logging(
    level=pick(
        prod=LogLevelOptions.INFO,
        test=LogLevelOptions.INFO,
        dev=LogLevelOptions.DEBUG,
        local=LogLevelOptions.DEBUG,
    ),
)
```
The `pick()` helper selects the right level based on `APP_ENV`.

**2. Explicit App Setup**
```python
from svc_infra.api.fastapi import APIVersionSpec, ServiceInfo, setup_service_api

app = setup_service_api(
    service=ServiceInfo(
        name="svc-infra-template",
        description="Example template service",
        release="0.1.0",
        contact=Contact(...),
        license=License(...),
    ),
    versions=[
        APIVersionSpec(
            tag="v1",
            routers_package="svc_infra_template.api.v1",
        )
    ],
)
```

This gives you full control over:
- Service metadata (appears in OpenAPI docs)
- Version configuration
- Router mounting
- Standard middlewares (request ID, exception handling)

### 2. Environment-Aware Configuration
Automatically configured based on `APP_ENV`:
- `local`/`dev`: DEBUG logs, plain format
- `prod`/`test`: INFO logs, JSON format

### 3. Versioned APIs
Routes are automatically prefixed:
- `/v1/ping` → `svc_infra_template.api.v1` router
- Future: `/v2/...` → just add to versions list

## Next Steps

Add more features from svc-infra:
- Database (SQLAlchemy + Alembic migrations)
- Authentication (FastAPI Users)
- Caching (Redis + Cashews)
- Rate limiting
- Webhooks
- Admin impersonation
- Data lifecycle management

See main svc-infra README for integration guides.
