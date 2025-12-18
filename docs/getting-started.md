# Getting Started

This guide will help you get started with svc-infra in your project.

## Installation

```bash
pip install svc-infra
```

### Optional Dependencies

svc-infra has several optional extras you can install:

| Extra | Description |
|-------|-------------|
| `pg` | PostgreSQL support (psycopg3 + asyncpg) |
| `pg2` | PostgreSQL v2 (legacy psycopg2) |
| `sqlite` | SQLite async support |
| `mysql` | MySQL support |
| `mongodb` | MongoDB support |
| `payments` | Stripe + Adyen billing |
| `stripe` | Stripe only |
| `s3` | AWS S3 storage |

Example with multiple extras:

```bash
pip install svc-infra[pg,payments,s3]
```

## Quick Start

### 1. Create a Basic Service

```python
from svc_infra import easy_service_app

# Create a FastAPI application with infrastructure configured
app = easy_service_app(name="MyService")

@app.get("/")
async def root():
    return {"message": "Hello, World!"}
```

### 2. Add Authentication

```python
from svc_infra.auth import setup_auth
from svc_infra.api.fastapi.dual.protected import user_router

# Setup auth with your app
setup_auth(app)

# Create protected routes
router = user_router(prefix="/api/v1", tags=["API"])

@router.get("/me")
async def get_current_user(user: CurrentUser):
    return {"user_id": user.id, "email": user.email}

app.include_router(router)
```

### 3. Add Database

```python
from svc_infra.db import init_db, get_session
from sqlalchemy import Column, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True)

# Initialize database
await init_db(url="postgresql+asyncpg://localhost/mydb")
```

### 4. Add Caching

```python
from svc_infra.cache import init_cache, cache_read, cache_write

# Initialize Redis cache
await init_cache(url="redis://localhost")

# Use cache decorators
@cache_read(ttl=300)  # 5 minutes
async def get_user_profile(user_id: str):
    return await fetch_from_db(user_id)
```

## Project Structure

Recommended project structure when using svc-infra:

```
my-service/
├── src/
│   └── my_service/
│       ├── __init__.py
│       ├── main.py          # App entry point
│       ├── config.py        # Settings
│       ├── models/          # SQLAlchemy models
│       ├── routes/          # API routes
│       ├── services/        # Business logic
│       └── schemas/         # Pydantic schemas
├── migrations/              # Alembic migrations
├── tests/
├── pyproject.toml
└── README.md
```

## Next Steps

- [API Framework](api.md) - Learn about the API framework
- [Authentication](auth.md) - Configure authentication
- [Database](database.md) - Set up your database
- [Caching](cache.md) - Add caching to your service
