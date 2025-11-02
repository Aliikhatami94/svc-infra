# Scaffold CLI Reference

The svc-infra CLI provides powerful scaffolding commands to automatically generate SQLAlchemy models and Pydantic schemas.

## Overview

The scaffold commands generate production-ready code with:
- ✅ ModelBase inheritance (proper for migrations)
- ✅ UUID primary keys with GUID type
- ✅ Timestamps (created_at, updated_at with server defaults)
- ✅ Optional tenant isolation (multi-tenancy)
- ✅ Optional soft delete support
- ✅ Unique constraint handling with case-insensitive indexes
- ✅ Service factory with deduplication logic
- ✅ Pydantic schemas (Create, Read, Update) with proper validation

## Commands

### 1. scaffold-models

Generate SQLAlchemy model files.

```bash
poetry run python -m svc_infra.cli sql scaffold-models \
  --dest-dir=src/app/db \
  --kind=entity \
  --entity-name=Product \
  --table-name=products \
  --include-tenant \
  --include-soft-delete
```

**Options:**
- `--dest-dir` (required): Destination directory for models
- `--kind`: `entity` (default) or `auth` (specialized user model)
- `--entity-name`: Class name (e.g., `Product`, `Order`, `Customer`)
- `--table-name`: Table name (defaults to plural snake_case of entity)
- `--include-tenant/--no-include-tenant`: Add `tenant_id` field (default: true)
- `--include-soft-delete/--no-include-soft-delete`: Add `deleted_at` field (default: false)
- `--overwrite/--no-overwrite`: Overwrite if exists (default: no-overwrite)
- `--models-filename`: Custom filename (default: `<snake_case_entity>.py`)

**Generated Model Structure (Entity):**
```python
from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID

class Product(ModelBase):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

# Automatic unique index (case-insensitive) on name, scoped by tenant
# Service factory with deduplication logic
```

### 2. scaffold-schemas

Generate Pydantic schema files.

```bash
poetry run python -m svc_infra.cli sql scaffold-schemas \
  --dest-dir=src/app/schemas \
  --kind=entity \
  --entity-name=Product \
  --include-tenant
```

**Options:**
- `--dest-dir` (required): Destination directory for schemas
- `--kind`: `entity` or `auth`
- `--entity-name`: Class name
- `--include-tenant/--no-include-tenant`: Add `tenant_id` field
- `--overwrite/--no-overwrite`: Overwrite if exists
- `--schemas-filename`: Custom filename (default: `<snake_case_entity>.py`)

**Generated Schema Structure:**
```python
from pydantic import BaseModel, ConfigDict

class ProductBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    description: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)

class ProductRead(ProductBase, Timestamped):
    id: UUID

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = None
    extra: Optional[Dict[str, Any]] = None
```

### 3. scaffold (Combined)

Generate both models and schemas together.

```bash
poetry run python -m svc_infra.cli sql scaffold \
  --kind=entity \
  --entity-name=Product \
  --table-name=products \
  --models-dir=src/app/db \
  --schemas-dir=src/app/schemas \
  --include-tenant \
  --include-soft-delete
```

**Additional Options:**
- `--same-dir/--no-same-dir`: Put models & schemas in same directory (creates `models.py` and `schemas.py`)
- `--models-filename`: Custom filename for models (when not using same-dir)
- `--schemas-filename`: Custom filename for schemas (when not using same-dir)

## Auth Scaffolding

For user authentication models:

```bash
poetry run python -m svc_infra.cli sql scaffold-models \
  --dest-dir=src/app/auth \
  --kind=auth \
  --entity-name=User \
  --table-name=users
```

**Generated Auth Model Includes:**
- User identity (id, email, full_name)
- Authentication (password_hash, last_login, disabled_reason)
- Authorization (is_active, is_superuser, is_verified, roles)
- Multi-tenancy (tenant_id)
- MFA/TOTP support (mfa_enabled, mfa_secret, mfa_confirmed_at, mfa_recovery)
- OAuth provider accounts relationship
- Refresh token encryption (using Fernet)
- Session management
- API key support
- Password policy enforcement
- Account lockout after failed attempts

**Generated Auth Schema Extends:**
- `fastapi_users.BaseUser[UUID]`
- `fastapi_users.BaseUserCreate`
- `fastapi_users.BaseUserUpdate`

## Complete Example Workflow

### 1. Scaffold a New Entity

```bash
# 1. Create models
poetry run python -m svc_infra.cli sql scaffold-models \
  --dest-dir=src/svc_infra_template/db \
  --kind=entity \
  --entity-name=Product \
  --table-name=products \
  --include-tenant \
  --include-soft-delete

# 2. Create schemas
poetry run python -m svc_infra.cli sql scaffold-schemas \
  --dest-dir=src/svc_infra_template/db \
  --kind=entity \
  --entity-name=Product \
  --include-tenant

# 3. Create tables
poetry run python create_tables.py
```

### 2. Use with SqlResource for Auto-CRUD

```python
# main.py
from svc_infra.api.fastapi.db.sql.add import add_sql_resources
from svc_infra.db.sql.resource import SqlResource
from svc_infra_template.db.product import Product
from svc_infra_template.db.product import (
    ProductCreate, ProductRead, ProductUpdate
)

add_sql_resources(
    app,
    resources=[
        SqlResource(
            model=Product,
            prefix="/products",
            tags=["Products"],
            soft_delete=True,
            search_fields=["name", "description"],
            ordering_default="-created_at",
            read_schema=ProductRead,
            create_schema=ProductCreate,
            update_schema=ProductUpdate,
            tenant_field="tenant_id",  # Automatically scopes by tenant
        ),
    ],
)
```

This generates:
- `POST /_sql/products` - Create product
- `GET /_sql/products` - List with pagination, search, ordering, tenant filtering
- `GET /_sql/products/{id}` - Get by ID
- `PATCH /_sql/products/{id}` - Update
- `DELETE /_sql/products/{id}` - Soft delete (if enabled)

### 3. With Custom Service Factory

The generated model includes a `create_entity_service` factory:

```python
from svc_infra.db.sql.repository import SqlRepository
from svc_infra_template.db.product import Product, create_entity_service

# In your dependency injection
async def get_product_service(
    repo: SqlRepository = Depends(get_repo)
) -> ProductService:
    return create_entity_service(
        repo,
        unique_ci=("name",),  # Case-insensitive uniqueness
        tenant_field="tenant_id",
        # Add custom pre-hooks if needed
        extra_pre_create=lambda data: {**data, "created_by": current_user.id},
    )

# Use in routes
@router.post("/products")
async def create_product(
    data: ProductCreate,
    service = Depends(get_product_service),
):
    return await service.create(data.model_dump())
```

## Advanced Features

### Uniqueness Constraints

Generated models include functional unique indexes:

```python
# Automatically generated in model
for _ix in make_unique_sql_indexes(
    Product,
    unique_ci=["name"],  # Case-insensitive
    tenant_field="tenant_id"  # Scoped by tenant
):
    pass  # Registers with SQLAlchemy metadata
```

The service factory enforces these and returns 409 with clear messages:
```json
{
  "detail": "Record with name='Widget' already exists."
}
```

### Payload Normalization

The generated service includes pre-hooks:

```python
def _map_entity_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(data)
    # Schema uses 'metadata', model uses 'extra'
    if "metadata" in d:
        d["extra"] = d.pop("metadata")
    # Trim whitespace from name
    if "name" in d and isinstance(d["name"], str):
        d["name"] = d["name"].strip()
    return d
```

Extend with custom logic:

```python
def my_pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
    # Add audit fields
    data["created_by"] = current_user.id
    data["organization_id"] = current_user.org_id
    return data

service = create_entity_service(
    repo,
    extra_pre_create=my_pre_create,
)
```

## Templates

Templates are located in `src/svc_infra/db/sql/templates/models_schemas/`:

- `entity/models.py.tmpl` - Generic entity model
- `entity/schemas.py.tmpl` - Generic entity schemas
- `auth/models.py.tmpl` - User authentication model
- `auth/schemas.py.tmpl` - User authentication schemas

Template variables:
- `${Entity}` - PascalCase entity name
- `${table_name}` - snake_case table name
- `${AuthEntity}` - PascalCase auth entity name
- `${auth_table_name}` - Auth table name
- `${tenant_field}` - Tenant field if enabled
- `${soft_delete_field}` - Soft delete fields if enabled
- `${tenant_arg}` - Tenant arg for service factory
- `${tenant_default}` - Default tenant field value

## Best Practices

1. **Always use scaffold for new entities** - Ensures consistency and includes all best practices
2. **Use ModelBase** - Generated models use `svc_infra.db.sql.base.ModelBase` for proper migration support
3. **Leverage tenant_field** - Enable multi-tenancy by default, disable only if truly single-tenant
4. **Use soft delete for important data** - Set `--include-soft-delete` for records that shouldn't be hard deleted
5. **Customize via service factories** - Use pre-hooks instead of modifying generated code
6. **Keep schemas separate** - Use `--models-dir` and `--schemas-dir` to maintain separation
7. **Version your scaffolds** - Treat generated code as source, commit to git

## Troubleshooting

### "No module named 'svc_infra'"
Make sure you're in the correct Poetry environment:
```bash
poetry install
poetry run python -m svc_infra.cli sql scaffold-models ...
```

### Generated files already exist
Use `--overwrite` flag to regenerate:
```bash
poetry run python -m svc_infra.cli sql scaffold-models --overwrite ...
```

### Table name conflicts
Specify explicit table name:
```bash
--table-name=my_custom_table_name
```

### Need custom field types
Edit the generated file - it's your code now! The scaffold provides a starting point.

## See Also

- [DATABASE.md](DATABASE.md) - Database setup guide
- [CLI.md](CLI.md) - Complete CLI reference
- [SqlResource documentation](../../src/svc_infra/db/sql/README.md) - Auto-CRUD details
