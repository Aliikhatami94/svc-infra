# Database Resource Management

svc-infra provides a simple way to mount CRUD APIs for your SQLAlchemy models with minimal boilerplate.

The two main pieces are:
- **Resource** – describes how a model should be exposed
- **include_resources(app, resources)** – registers CRUD routers into your FastAPI app

---

## Quick Start

### 1. Define your SQLAlchemy models

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, func
from datetime import datetime
from typing import Optional

class Base(DeclarativeBase):
    pass

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

---

### 2. Attach resources to FastAPI

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.db.sql import include_resources, SqlResource

app = FastAPI(title="My API")

include_resources(
    app,
    resources=[
        SqlResource(
            model=Project,
            prefix="/projects",
            tags=["projects"],
            soft_delete=True,                     # enables soft-delete endpoints
            search_fields=["name", "description"],
            ordering_default="-created_at",
            allowed_order_fields=["name", "created_at", "updated_at"],
        ),
    ],
)
```

---

### 3. Run your app

```bash
uvicorn app:app --reload
```

Now you have endpoints under `/_sql/projects`:
- `GET /_sql/projects` – list with pagination, search, ordering
- `POST /_sql/projects` – create
- `GET /_sql/projects/{id}` – retrieve
- `PATCH /_sql/projects/{id}` – update
- `DELETE /_sql/projects/{id}` – delete (soft-delete if enabled)

---

## Advanced Usage

### Custom Pydantic Schemas

If you want to provide your own request/response models, pass them directly:

```python
SqlResource(
    model=Project,
    prefix="/projects",
    read_schema=ProjectRead,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
)
```

Otherwise, schemas are auto-generated from your SQLAlchemy model.

### Multiple Resources

You can register as many as you need:

```python
include_resources(app, [
    SqlResource(model=Project, prefix="/projects"),
    SqlResource(model=Task, prefix="/tasks"),
])
```

---

## Notes

- Routers mount under `/_sql` by default (e.g., `/_sql/projects`)
- Searching and ordering work automatically if you configure `search_fields`, `ordering_default`, and `allowed_order_fields`
- Soft delete requires a `deleted_at` column in your model

---

⚡ **With just a model and a Resource definition, you get a full CRUD API for free.**
