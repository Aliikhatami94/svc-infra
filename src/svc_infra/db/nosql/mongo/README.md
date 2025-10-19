# MongoDB: Scaffold • Prepare (migrate) • Integrate (FastAPI) • Use

This guide shows how to:

1) scaffold documents/schemas/resources with our CLI
2) prepare the database (create collections + apply indexes) with our CLI
3) integrate Mongo into a FastAPI app
4) call the generated CRUD endpoints

> Works whether you provide **explicit Pydantic schemas** or let the system **auto-derive** them from your document model.

---

## Prerequisites

- Python 3.11+
- MongoDB (local or cloud)
- Environment:
    - `MONGO_URL` – e.g. `mongodb://localhost:27017`
    - `MONGO_DB` – e.g. `my_app_db`

You can place these in your shell or a `.env` that your app loads.

---

## 1) Scaffolding (CLI)

We provide four CLI commands. You can register them on your Typer app or invoke directly if your tooling already exposes them.

### Commands

- `mongo scaffold` — create both document **and** CRUD schemas
- `mongo scaffold-documents` — create only the **document** model (Pydantic)
- `mongo scaffold-schemas` — create only the **CRUD schemas**
- `mongo scaffold-resources` — create a starter `resources.py` with a `RESOURCES` list

### Typical usage

#### A) Scaffold documents + schemas together

```bash
yourapp mongo scaffold \
  --entity-name Product \
  --documents-dir ./src/your_app/products \
  --schemas-dir ./src/your_app/products \
  --same-dir \
  --overwrite
```

This creates something like:

```text
src/your_app/products/documents.py   # ProductDoc (__collection__=”products”)
src/your_app/products/schemas.py     # ProductRead/ProductCreate/ProductUpdate
```

B) Documents only

```bash
yourapp mongo scaffold-documents \
  --dest-dir ./src/your_app/products \
  --entity-name Product \
  --documents-filename product_doc.py
```

C) Schemas only

```bash
yourapp mongo scaffold-schemas \
  --dest-dir ./src/your_app/products \
  --entity-name Product \
  --schemas-filename product_schemas.py
```

D) Starter resources.py

```bash
yourapp mongo scaffold-resources \
  --dest-dir ./src/your_app/mongo \
  --filename resources.py \
  --overwrite
```

Tip: You can regenerate with --overwrite while iterating.

⸻

## 2) Prepare the DB (migrate)

“Prepare” connects to Mongo, verifies the database, ensures collections exist, and applies indexes defined on each NoSqlResource.indexes (via pymongo.IndexModel).

Where do indexes live?

Directly on your NoSqlResource:

```python
# src/your_app/mongo/resources.py
from pymongo import ASCENDING, IndexModel
from pymongo.collation import Collation
from svc_infra.db.nosql.resource import NoSqlResource
from your_app.products.documents import ProductDoc

RESOURCES = [
    NoSqlResource(
        prefix="/products",
        document_model=ProductDoc,                # or explicit schemas, see below
        search_fields=["name"],
        tags=["products"],
        soft_delete=True,
        soft_delete_field="deleted_at",
        indexes=[
            IndexModel(
                [("tenant_id", ASCENDING), ("name", ASCENDING)],
                name="uq_products_tenant_name_ci",
                unique=True,
                collation=Collation(locale="en", strength=2),  # case-insensitive
            ),
            IndexModel(
                [("tenant_id", ASCENDING), ("created_at", ASCENDING)],
                name="ix_products_tenant_created_at",
            ),
        ],
    ),
]
```

Prepare with the CLI

There are two flavors:

A) Async, minimal (connect, create collections, apply indexes)

```bash
yourapp mongo prepare \
  --resources your_app.mongo.resources:RESOURCES \
  --mongo-url "$MONGO_URL" \
  --mongo-db "$MONGO_DB"
```

B) Synchronous wrapper (end-to-end convenience)

```bash
yourapp mongo setup-and-prepare \
  --resources your_app.mongo.resources:RESOURCES \
  --mongo-url "$MONGO_URL" \
  --mongo-db "$MONGO_DB"
```

You can also ping connectivity:

```bash
yourapp mongo ping --mongo-url "$MONGO_URL" --mongo-db "$MONGO_DB"
```

Behind the scenes, preparation also locks a service ID to a DB name to prevent accidental cross-DB usage. You can pass --allow-rebind if you intentionally move environments.

⸻

## 3) Integrate with FastAPI

Add Mongo lifecycle, health, and the auto CRUD routers.

```python
# src/your_app/main.py
from fastapi import FastAPI
from svc_infra.api.fastapi.db.add import add_mongo_db, add_mongo_health, add_mongo_resources
from svc_infra.app.logging import setup_logging, LogLevelOptions
from svc_infra.app.env import pick
from your_app.mongo.resources import RESOURCES

setup_logging(level=pick(
    prod=LogLevelOptions.INFO,
    test=LogLevelOptions.INFO,
    dev=LogLevelOptions.DEBUG,
    local=LogLevelOptions.DEBUG,
))

app = FastAPI(title="your_app")

# 1) Mongo client lifecycle (reads MONGO_URL, MONGO_DB)
add_mongo_db(app)

# 2) Health endpoint
add_mongo_health(app, prefix="/_mongo/health", include_in_schema=False)

# 3) CRUD endpoints (derived from RESOURCES)
add_mongo_resources(app, resources=RESOURCES)
```

Run your server:

```bash
uvicorn your_app.main:app --reload --port 8000
```

Health check:

```text
GET http://localhost:8000/_mongo/health
```

⸻

## 4) Documents vs Schemas (how they’re wired)

You have two options for each resource:

Option A: Auto-schemas (recommended to start)

Provide only a document model (Pydantic). We auto-derive Read/Create/Update and ensure ObjectId is JSON-safe.

```python
# documents.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from svc_infra.db.nosql.types import PyObjectId

class ProductDoc(BaseModel):
    __collection__ = "products"
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name: str
    is_active: bool = True
    tenant_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "from_attributes": True,
        "json_encoders": {PyObjectId: str},
    }
```

In RESOURCES, pass document_model=ProductDoc.
The framework will derive CRUD schemas and mount / _mongo/products.

Option B: Explicit schemas (when you need strict shapes)

```python
# schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from svc_infra.db.nosql.types import PyObjectId

class ProductRead(BaseModel):
    id: Optional[PyObjectId] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    tenant_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
        "json_encoders": {PyObjectId: str},
    }

class ProductCreate(BaseModel):
    name: str
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = None
```

Then in your RESOURCES, set read_schema=..., create_schema=..., update_schema=... instead of document_model=.

Note on ObjectId JSON
The repository returns {"id": "<hex string>"} so responses are JSON-safe by default. Our auto-schemas also expose id as str (not raw ObjectId) to avoid serialization issues. If you write explicit schemas using PyObjectId, ensure your model’s model_config.json_encoders includes {PyObjectId: str} (as above).

⸻

## 5) Endpoints & Examples

Assuming prefix="/products" and default mount under the DB prefix:

Base path: /_mongo/products

List

```text
GET /_mongo/products?limit=50&offset=0
```

Response:

```json
{
  "total": 2,
  "limit": 50,
  "offset": 0,
  "items": [
    {"id":"68c5c30a4bb58d016a412dc1","name":"Oranges","is_active":true,"tenant_id":null,"created_at":null,"updated_at":null},
    {"id":"68c5c36a4bb58d016a412e99","name":"Apples","is_active":true}
  ]
}
```

Search (case-insensitive regex on configured fields):

```text
GET /_mongo/products?q=ora
```

Order:

```text
GET /_mongo/products?order_by=name,-created_at
```

Get by id

```text
GET /_mongo/products/{id}
```

Create

```text
POST /_mongo/products
Content-Type: application/json
```

```json
{
  "name": "Bananas",
  "tenant_id": "T1"
}
```

Update (partial)

```text
PATCH /_mongo/products/{id}
Content-Type: application/json
```

```json
{
  "is_active": false
}
```

Delete

Soft-delete if enabled on the resource (sets deleted_at and optional flag), otherwise hard delete:

```text
DELETE /_mongo/products/{id}
```

⸻

## 6) Soft Delete Behavior

If a resource sets:

soft_delete=True
soft_delete_field="deleted_at"
soft_delete_flag_field=None or "is_alive"  # optional

	•	List/Search/Get filter out soft-deleted records by default.
	•	Delete sets deleted_at=now() (and flips the flag false if configured).

⸻

## 7) Programmatic app wiring (alternate)

If you prefer explicit URL/DB without env:

```python
from svc_infra.api.fastapi.db.add import add_mongo_db_with_url

add_mongo_db_with_url(
    app,
    url="mongodb://localhost:27017",
    db_name="my_app_db",
)
```

⸻

## 8) Resource Options (cheatsheet)

```python
NoSqlResource(
  collection=None,                 # inferred from document_model.__collection__ or class name
  prefix="/products",              # router path under "/_mongo"
  document_model=ProductDoc,       # OR pass explicit schemas:
  # read_schema=ProductRead,
  # create_schema=ProductCreate,
  # update_schema=ProductUpdate,

  search_fields=["name"],          # fields used by ?q=...
  tags=["products"],

  id_field="_id",
  soft_delete=True,
  soft_delete_field="deleted_at",
  soft_delete_flag_field=None,

  service_factory=None,            # custom service if needed

  # generated schema naming / exclusions if auto-schemas are used
  read_name=None,
  create_name=None,
  update_name=None,
  create_exclude=("_id",),
  read_exclude=(),
  update_exclude=(),

  # Indexes declared inline (pymongo.IndexModel or alias dicts)
  indexes=[
    # IndexModel([...], name="...", unique=..., collation=..., expireAfterSeconds=..., partialFilterExpression=...)
  ],
)
```

⸻

## 9) Troubleshooting
	•	500 with PydanticSerializationError: bson.objectid.ObjectId
	•	Ensure your repository returns id as string (this is already done in our repo).
	•	If using explicit schemas with PyObjectId, make sure model_config.json_encoders includes {PyObjectId: str}.
	•	When using auto-schemas, we expose ObjectId-like fields as str so no custom encoder is needed.
	•	Connected to wrong DB name
  •	The system locks a service_id to the DB name once prepared. If you change DBs, run `mongo prepare` with --allow-rebind.
	•	Indexes not created
  •	Double-check RESOURCES[indexes]. Run `mongo prepare` again and inspect the output dictionary of created indexes.

⸻

## 10) Example Project Layout

```text
src/
  your_app/
    main.py
    mongo/
      resources.py
    products/
      documents.py
      schemas.py
```

⸻

## 11) Quick Start (copy/paste)

```bash
# 1) Scaffold
yourapp mongo-scaffold \
  --entity-name Product \
  --documents-dir ./src/your_app/products \
  --schemas-dir ./src/your_app/products \
  --same-dir \
  --overwrite

# 2) Add a resource pointing to ProductDoc or explicit schemas
#    (edit src/your_app/mongo/resources.py)

# 3) Prepare DB
export MONGO_URL="mongodb://localhost:27017"
export MONGO_DB="your_app_db"
yourapp mongo-prepare \
  --resources your_app.mongo.resources:RESOURCES

# 4) Run FastAPI
uvicorn your_app.main:app --reload --port 8000

# 5) Call endpoints
curl http://localhost:8000/_mongo/products
curl -XPOST http://localhost:8000/_mongo/products -H 'content-type: application/json' -d '{"name":"Grapes"}'
```
