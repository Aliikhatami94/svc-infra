# API Documentation & SDK Generation

**svc-infra** provides automatic API documentation with OpenAPI enrichment and SDK generation for TypeScript, Python, and Postman.

---

## Quick Start

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.docs.add import add_docs

app = FastAPI(title="My API", version="1.0.0")

# Mount docs at /docs, /redoc, /openapi.json
add_docs(app)

# Optional: Export OpenAPI schema to disk on startup
add_docs(app, export_openapi_to="openapi.json")
```

---

## Enabling Documentation

### Basic Setup

```python
from svc_infra.api.fastapi.docs.add import add_docs

add_docs(
    app,
    swagger_url="/docs",       # Swagger UI
    redoc_url="/redoc",        # ReDoc
    openapi_url="/openapi.json",  # Raw OpenAPI schema
    landing_url="/",           # Landing page (or /_docs if / taken)
    include_landing=True,      # Show landing with links to docs
)
```

### Auto-Mounted Routes

When you call `add_docs(app)`, these routes become available:

| Route | Description |
|-------|-------------|
| `/docs` | Interactive Swagger UI |
| `/redoc` | ReDoc documentation viewer |
| `/openapi.json` | Raw OpenAPI 3.x schema |
| `/` or `/_docs` | Landing page with doc links |

### Dark Mode

Append `?theme=dark` to enable a minimal dark mode:

```bash
# Dark Swagger UI
http://localhost:8000/docs?theme=dark

# Dark ReDoc
http://localhost:8000/redoc?theme=dark
```

### setup_service_api Integration

For versioned apps, docs are auto-mounted:

```python
from svc_infra.api.fastapi.setup import setup_service_api

app = setup_service_api(
    service_name="my-service",
    release="1.0.0",
    # Docs automatically available at /docs, /redoc, /openapi.json
)
```

---

## OpenAPI Enrichment

The OpenAPI pipeline automatically adds metadata through a series of mutators.

### Automatic Enhancements

| Enhancement | Description |
|-------------|-------------|
| `x-codeSamples` | curl and httpie examples per operation |
| Problem+JSON | Error response examples (4xx/5xx) |
| Standard responses | Common error schemas (400, 401, 403, 404, 500) |
| Pagination | Cursor/page parameters and envelope schemas |
| Security schemes | JWT Bearer and API Key auth |
| Header parameters | ETag, Last-Modified, X-Request-Id |

### x-codeSamples Generation

Every operation gets auto-generated code samples:

```yaml
# Generated in OpenAPI spec
/v1/projects:
  get:
    x-codeSamples:
      - lang: curl
        source: |
          curl -X GET 'http://localhost:8000/v1/projects' \
            -H 'Authorization: Bearer <token>'
      - lang: httpie
        source: |
          http GET http://localhost:8000/v1/projects \
            Authorization:'Bearer <token>'
```

### Problem+JSON Examples

Error responses automatically include RFC 9457 Problem+JSON examples:

```yaml
responses:
  "400":
    content:
      application/problem+json:
        schema:
          $ref: "#/components/schemas/Problem"
        example:
          type: "https://api.example.com/problems/validation-error"
          title: "Bad Request"
          status: 400
          detail: "Request validation failed"
```

### Custom Mutators

Add your own OpenAPI transformations:

```python
from svc_infra.api.fastapi.openapi.mutators import setup_mutators
from svc_infra.api.fastapi.openapi.models import ServiceInfo, APIVersionSpec

def my_custom_mutator():
    """Add custom metadata to all operations."""
    def mutate(schema: dict) -> dict:
        schema = dict(schema)
        info = schema.setdefault("info", {})
        info["x-custom-header"] = "My Custom Value"
        return schema
    return mutate

# Get default mutators
mutators = setup_mutators(
    service=ServiceInfo(name="my-service", release="1.0.0"),
    spec=None,
    include_api_key=True,
    server_url="https://api.example.com",
)

# Add your custom mutator
mutators.append(my_custom_mutator())
```

---

## Exporting OpenAPI

### On Startup

```python
add_docs(app, export_openapi_to="openapi.json")
# Creates openapi.json in working directory on app startup
```

### Nested Path

```python
add_docs(app, export_openapi_to="docs/api/openapi.json")
# Automatically creates parent directories
```

### CI/CD Export Pattern

```yaml
# .github/workflows/openapi.yml
name: Export OpenAPI
on:
  push:
    branches: [main]

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start app and export schema
        run: |
          # App exports openapi.json on startup, then exits
          timeout 10 python -c "
          from myapp import create_app
          app = create_app()
          # Schema exported via add_docs(export_openapi_to=...)
          " || true

      - name: Commit schema
        run: |
          git add openapi.json
          git commit -m "Update OpenAPI schema" || true
          git push
```

### CLI Export

```bash
# Export via dx command
svc-infra dx openapi --app myapp:app --output openapi.json
```

---

## SDK Generation

Generate client SDKs from your OpenAPI schema using the CLI.

### TypeScript SDK

```bash
# Dry-run (preview command)
svc-infra sdk ts openapi.json

# Generate SDK
svc-infra sdk ts openapi.json --dry-run=false --outdir sdk-ts
```

**Output structure:**
```
sdk-ts/
├── core/
│   ├── ApiError.ts
│   ├── ApiRequestOptions.ts
│   ├── ApiResult.ts
│   └── request.ts
├── models/
│   ├── Project.ts
│   └── User.ts
├── services/
│   ├── ProjectsService.ts
│   └── UsersService.ts
└── index.ts
```

**Usage in client code:**
```typescript
import { ProjectsService } from './sdk-ts';

const projects = await ProjectsService.listProjects({
  limit: 10,
  cursor: undefined,
});
```

### Python SDK

```bash
# Dry-run (preview command)
svc-infra sdk py openapi.json

# Generate SDK with custom package name
svc-infra sdk py openapi.json \
  --dry-run=false \
  --outdir sdk-py \
  --package-name my_api_client
```

**Output structure:**
```
sdk-py/
├── my_api_client/
│   ├── __init__.py
│   ├── api/
│   │   ├── projects_api.py
│   │   └── users_api.py
│   ├── models/
│   │   ├── project.py
│   │   └── user.py
│   └── api_client.py
├── setup.py
└── requirements.txt
```

**Usage in client code:**
```python
from my_api_client import ApiClient, ProjectsApi

client = ApiClient()
client.configuration.host = "https://api.example.com"
client.configuration.access_token = "your-token"

api = ProjectsApi(client)
projects = api.list_projects(limit=10)
```

### Postman Collection

```bash
# Dry-run (preview command)
svc-infra sdk postman openapi.json

# Generate collection
svc-infra sdk postman openapi.json \
  --dry-run=false \
  --out postman_collection.json
```

**Import into Postman:**
1. Open Postman
2. File → Import → Upload Files
3. Select `postman_collection.json`
4. All endpoints are ready with examples

---

## Publishing SDKs

### npm (TypeScript)

```yaml
# .github/workflows/publish-ts-sdk.yml
name: Publish TS SDK
on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://registry.npmjs.org'

      - name: Generate SDK
        run: |
          svc-infra sdk ts openapi.json --dry-run=false --outdir sdk-ts

      - name: Publish
        working-directory: sdk-ts
        run: |
          npm init -y
          npm version ${{ github.event.release.tag_name }}
          npm publish --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

### PyPI (Python)

```yaml
# .github/workflows/publish-py-sdk.yml
name: Publish Python SDK
on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Generate SDK
        run: |
          svc-infra sdk py openapi.json \
            --dry-run=false \
            --outdir sdk-py \
            --package-name my_api_client

      - name: Build and publish
        working-directory: sdk-py
        run: |
          pip install build twine
          python -m build
          twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

### Versioning Strategy

```bash
# Match SDK version to API version
# In your release workflow:
API_VERSION=$(grep '"version"' openapi.json | head -1 | cut -d'"' -f4)
npm version $API_VERSION
# or
sed -i "s/version=.*/version='$API_VERSION',/" setup.py
```

---

## Client Examples

### curl

```bash
# GET request
curl -X GET 'http://localhost:8000/v1/projects' \
  -H 'Authorization: Bearer <token>'

# POST with JSON body
curl -X POST 'http://localhost:8000/v1/projects' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"name": "My Project", "description": "A new project"}'

# With pagination
curl -X GET 'http://localhost:8000/v1/projects?limit=10&cursor=abc123' \
  -H 'Authorization: Bearer <token>'
```

### httpie

```bash
# GET request
http GET http://localhost:8000/v1/projects \
  Authorization:'Bearer <token>'

# POST with JSON
http POST http://localhost:8000/v1/projects \
  Authorization:'Bearer <token>' \
  name="My Project" \
  description="A new project"
```

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "your-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# GET
response = requests.get(f"{BASE_URL}/v1/projects", headers=headers)
projects = response.json()

# POST
response = requests.post(
    f"{BASE_URL}/v1/projects",
    headers=headers,
    json={"name": "My Project"},
)
new_project = response.json()
```

### TypeScript (fetch)

```typescript
const BASE_URL = "http://localhost:8000";
const TOKEN = "your-token";

// GET
const response = await fetch(`${BASE_URL}/v1/projects`, {
  headers: { Authorization: `Bearer ${TOKEN}` },
});
const projects = await response.json();

// POST
const createResponse = await fetch(`${BASE_URL}/v1/projects`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ name: "My Project" }),
});
const newProject = await createResponse.json();
```

---

## Production Recommendations

### Documentation Security

```python
from svc_infra.app.env import pick

# Disable docs in production
if pick(prod=False, nonprod=True):
    add_docs(app)
```

### OpenAPI Validation

```bash
# Validate schema before publishing
npx @redocly/cli lint openapi.json

# Check for breaking changes
npx @redocly/cli bundle openapi.json --output bundled.json
```

### SDK Testing

```python
# Test generated SDK against your API
import pytest
from my_api_client import ApiClient, ProjectsApi

@pytest.fixture
def api():
    client = ApiClient()
    client.configuration.host = "http://localhost:8000"
    return ProjectsApi(client)

def test_list_projects(api):
    projects = api.list_projects(limit=10)
    assert isinstance(projects, list)
```

---

## Troubleshooting

### Docs Not Visible at `/`

**Symptom:** Landing page not appearing at root.

**Cause:** Your app already has a route at `/`.

**Solution:** Docs are mounted at `/_docs` instead:
```
http://localhost:8000/_docs
```

### Dark Mode Not Applying

**Symptom:** Theme parameter ignored.

**Solution:** Use the query parameter:
```
http://localhost:8000/docs?theme=dark
```

### Missing Problem Examples

**Symptom:** Error responses lack examples.

**Diagnosis:**
1. Ensure error handlers use the `Problem` schema
2. Verify `setup_mutators()` runs (automatic in `setup_service_api`)

**Solution:**
```python
from svc_infra.api.fastapi.setup import setup_service_api

# Mutators run automatically
app = setup_service_api(service_name="my-service", release="1.0.0")
```

### SDK Generation Fails

**Symptom:** `npx` command errors.

**Prerequisites:**
- Node.js installed
- npx available in PATH

**Solution:**
```bash
# Install Node.js
brew install node  # macOS
apt install nodejs npm  # Ubuntu

# Verify
node --version
npx --version
```

### OpenAPI Export Empty

**Symptom:** `openapi.json` is empty or incomplete.

**Cause:** Routes not registered before export.

**Solution:** Ensure routes are registered before calling `add_docs`:
```python
from fastapi import FastAPI
from svc_infra.api.fastapi.docs.add import add_docs

app = FastAPI()

# Register routes FIRST
@app.get("/v1/projects")
async def list_projects():
    return []

# THEN add docs
add_docs(app, export_openapi_to="openapi.json")
```

---

## API Reference

### add_docs

```python
def add_docs(
    app: FastAPI,
    *,
    redoc_url: str = "/redoc",
    swagger_url: str = "/docs",
    openapi_url: str = "/openapi.json",
    export_openapi_to: str | None = None,
    landing_url: str = "/",
    include_landing: bool = True,
) -> None:
    """Enable docs endpoints and optionally export OpenAPI schema to disk."""
```

### setup_mutators

```python
def setup_mutators(
    service: ServiceInfo,
    spec: APIVersionSpec | None,
    include_api_key: bool = False,
    server_url: str | None = None,
) -> list:
    """Return list of OpenAPI mutators for enrichment."""
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `svc-infra sdk ts <openapi>` | Generate TypeScript SDK |
| `svc-infra sdk py <openapi>` | Generate Python SDK |
| `svc-infra sdk postman <openapi>` | Generate Postman collection |

---

## See Also

- [API Guide](api.md) — FastAPI integration patterns
- [CLI Reference](cli.md) — Full CLI documentation
- [Auth Guide](auth.md) — Authentication setup
- [Observability](observability.md) — Metrics and monitoring
