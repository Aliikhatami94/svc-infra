# Deployment Guide

Platform detection and environment resolution for deploying svc-infra applications to various cloud providers and PaaS platforms.

## Overview

svc-infra provides a comprehensive deployment utilities module:

- **Platform Detection**: Automatic detection of Railway, Render, Fly.io, Heroku, AWS, GCP, Azure
- **Environment Resolution**: Platform-aware database URLs, Redis URLs, and port binding
- **Service Discovery**: Internal service URL resolution for Kubernetes and PaaS
- **Environment Helpers**: Production/preview environment detection

## Quick Start

### Platform Detection

```python
from svc_infra.deploy import get_platform, Platform

# Auto-detect deployment platform
platform = get_platform()
print(platform)  # "railway", "aws_ecs", "cloud_run", "local", etc.

# Platform-specific logic
if platform == Platform.RAILWAY:
    print("Running on Railway!")
elif platform == Platform.KUBERNETES:
    print("Running in Kubernetes!")
```

### Server Binding

```python
import uvicorn
from svc_infra.deploy import get_host, get_port

# Automatically binds to 0.0.0.0 in containers, 127.0.0.1 locally
uvicorn.run(
    "app:app",
    host=get_host(),
    port=get_port(),  # Uses PORT env var or defaults to 8000
)
```

### Database URL Resolution

```python
from sqlalchemy.ext.asyncio import create_async_engine
from svc_infra.deploy import get_database_url

# Handles platform-specific URL resolution:
# - Railway: Prefers DATABASE_URL_PRIVATE for free egress
# - Heroku: Normalizes postgres:// to postgresql://
url = get_database_url()
if url:
    engine = create_async_engine(url)
```

---

## Platform Detection

### Supported Platforms

| Platform | Enum Value | Detection Variables |
|----------|------------|---------------------|
| **Developer PaaS** |||
| Railway | `Platform.RAILWAY` | `RAILWAY_ENVIRONMENT`, `RAILWAY_PROJECT_ID` |
| Render | `Platform.RENDER` | `RENDER`, `RENDER_SERVICE_ID` |
| Fly.io | `Platform.FLY` | `FLY_APP_NAME`, `FLY_REGION` |
| Heroku | `Platform.HEROKU` | `DYNO`, `HEROKU_APP_NAME` |
| **AWS** |||
| ECS/Fargate | `Platform.AWS_ECS` | `ECS_CONTAINER_METADATA_URI` |
| Lambda | `Platform.AWS_LAMBDA` | `AWS_LAMBDA_FUNCTION_NAME` |
| Elastic Beanstalk | `Platform.AWS_BEANSTALK` | `ELASTIC_BEANSTALK_ENVIRONMENT_NAME` |
| **Google Cloud** |||
| Cloud Run | `Platform.CLOUD_RUN` | `K_SERVICE`, `K_REVISION` |
| App Engine | `Platform.APP_ENGINE` | `GAE_APPLICATION`, `GAE_SERVICE` |
| GCE | `Platform.GCE` | `GCE_METADATA_HOST` |
| **Azure** |||
| Container Apps | `Platform.AZURE_CONTAINER_APPS` | `CONTAINER_APP_NAME` |
| Functions | `Platform.AZURE_FUNCTIONS` | `FUNCTIONS_WORKER_RUNTIME` |
| App Service | `Platform.AZURE_APP_SERVICE` | `WEBSITE_SITE_NAME` |
| **Container** |||
| Kubernetes | `Platform.KUBERNETES` | `KUBERNETES_SERVICE_HOST` |
| Docker | `Platform.DOCKER` | `/.dockerenv` file |
| Local | `Platform.LOCAL` | No cloud env vars detected |

### Helper Functions

```python
from svc_infra.deploy import (
    is_containerized,
    is_local,
    is_aws,
    is_gcp,
    is_azure,
    is_paas,
    is_serverless,
)

# Check if running in any containerized environment
if is_containerized():
    configure_for_container()  # Enable structured logging

# Check for local development
if is_local():
    enable_debug_mode()

# Cloud provider checks
if is_aws():
    setup_xray_tracing()
elif is_gcp():
    setup_cloud_trace()
elif is_azure():
    setup_app_insights()

# Developer PaaS check (Railway, Render, Fly, Heroku)
if is_paas():
    use_platform_managed_ssl()

# Serverless environment check (Lambda, Cloud Run, Functions)
if is_serverless():
    optimize_cold_start()
```

---

## URL Resolution

### Database URL

```python
from svc_infra.deploy import get_database_url

# Default: prefer private URLs, normalize for SQLAlchemy
url = get_database_url()

# Disable private URL preference (use public URL)
url = get_database_url(prefer_private=False)

# Disable URL normalization
url = get_database_url(normalize=False)
```

**Resolution Order:**

1. `DATABASE_URL_PRIVATE` (Railway private networking)
2. `DATABASE_URL` (standard)
3. `SQL_URL`, `DB_URL`, `PRIVATE_SQL_URL` (legacy svc-infra)

**Normalization:**

- Converts `postgres://` to `postgresql://` for SQLAlchemy compatibility
- Converts `postgres+asyncpg://` to `postgresql+asyncpg://`

### Redis URL

```python
from svc_infra.deploy import get_redis_url

# Prefer private networking
url = get_redis_url()

# Use public URL
url = get_redis_url(prefer_private=False)
```

**Resolution Order:**

1. `REDIS_URL_PRIVATE` or `REDIS_PRIVATE_URL`
2. `REDIS_URL`
3. `CACHE_URL`
4. `UPSTASH_REDIS_REST_URL`

---

## Service Discovery

### Internal Service URLs

```python
from svc_infra.deploy import get_service_url

# Get URL for internal "worker" service
worker_url = get_service_url("worker")
if worker_url:
    httpx.post(f"{worker_url}/jobs", json=job_data)

# With custom port and scheme
api_url = get_service_url("api", default_port=3000, scheme="https")
```

**Resolution:**

- Railway: `<SERVICE>_URL` env var
- Kubernetes: `<SERVICE>_SERVICE_HOST` + `<SERVICE>_SERVICE_PORT`
- Generic: `<SERVICE>_URL` env var

### Public URL

```python
from svc_infra.deploy import get_public_url

# Get this service's public HTTPS URL
public_url = get_public_url()
print(public_url)  # "https://my-app.railway.app"
```

**Resolution:**

| Platform | Method |
|----------|--------|
| Railway | `RAILWAY_PUBLIC_DOMAIN` |
| Render | `RENDER_EXTERNAL_URL` |
| Fly.io | `FLY_APP_NAME.fly.dev` |
| Heroku | `APP_URL` or `<app>.herokuapp.com` |

---

## Environment Detection

### Environment Name

```python
from svc_infra.deploy import get_environment_name, is_production, is_preview

# Get environment name
env = get_environment_name()
print(env)  # "production", "staging", "preview", "local"

# Quick checks
if is_production():
    enable_sentry()
    disable_debug_mode()

if is_preview():
    use_preview_database()
```

**Resolution:**

1. `RAILWAY_ENVIRONMENT` (Railway)
2. `IS_PULL_REQUEST` → "preview" (Render)
3. `APP_ENV`, `ENVIRONMENT`, `ENV` (generic)
4. Default: "local"

---

## Full Example

```python
from fastapi import FastAPI
from svc_infra.deploy import (
    get_platform,
    get_host,
    get_port,
    get_database_url,
    get_redis_url,
    is_production,
    is_containerized,
    Platform,
)
from svc_infra.logging import configure_for_container

app = FastAPI()

# Configure logging based on environment
if is_containerized():
    configure_for_container()

# Database setup
DATABASE_URL = get_database_url()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not configured")

# Redis setup (optional)
REDIS_URL = get_redis_url()

# Platform-specific configuration
platform = get_platform()
if platform == Platform.RAILWAY:
    # Railway-specific setup
    pass
elif platform == Platform.AWS_LAMBDA:
    # Lambda requires Mangum adapter
    from mangum import Mangum
    handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=get_host(),
        port=get_port(),
        log_level="info" if is_production() else "debug",
    )
```

---

## API Reference

### Platform Enum

::: svc_infra.deploy.Platform
    options:
      show_source: false

### Functions

| Function | Description |
|----------|-------------|
| `get_platform()` | Detect current deployment platform |
| `is_containerized()` | Check if running in a container |
| `is_local()` | Check if running locally |
| `is_aws()` | Check if running on AWS |
| `is_gcp()` | Check if running on Google Cloud |
| `is_azure()` | Check if running on Azure |
| `is_paas()` | Check if running on developer PaaS |
| `is_serverless()` | Check if running serverless |
| `get_port(default=8000)` | Get HTTP port from `PORT` env var |
| `get_host(default="127.0.0.1")` | Get host address (0.0.0.0 in containers) |
| `get_database_url(...)` | Get database URL with platform-aware resolution |
| `get_redis_url(...)` | Get Redis URL with platform-aware resolution |
| `get_service_url(name, ...)` | Get internal service URL |
| `get_public_url()` | Get this service's public URL |
| `get_environment_name()` | Get environment name (production, staging, etc.) |
| `is_production()` | Check if production environment |
| `is_preview()` | Check if preview/PR environment |
