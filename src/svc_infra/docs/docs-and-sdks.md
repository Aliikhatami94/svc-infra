# Docs & SDKs

This guide shows how to enable API docs, enrich your OpenAPI, and generate SDKs.

## Enabling docs

- Use `setup_service_api(...)` for versioned apps; root docs are auto-mounted in local/dev.
- For standalone FastAPI apps, call `add_docs(app)` to mount:
  - `/docs` (Swagger UI)
  - `/redoc` (ReDoc)
  - `/openapi.json` (OpenAPI schema)
  - A landing page at `/` listing root and scoped docs (falls back to `/_docs` if `/` is taken).

Tip: Append `?theme=dark` to `/docs` or `/redoc` for a minimal dark mode.

## OpenAPI enrichment

The OpenAPI pipeline adds helpful metadata automatically:
- `x-codeSamples` per operation (curl and httpie) using your server base URL.
- Problem+JSON examples on error responses (4xx/5xx) referencing the `Problem` schema.
- Existing success/media examples are preserved and normalized.

These mutators are applied for both root and versioned apps via `setup_mutators(...)`.

## Exporting OpenAPI

`add_docs(app, export_openapi_to="openapi.json")` writes the schema to disk on startup.

## Generate SDKs (CLI)

Use the CLI to generate SDKs from OpenAPI (defaults to dry-run, uses npx tools):

- TypeScript (openapi-typescript-codegen):
  svc-infra sdk ts openapi.json --outdir sdk-ts --dry-run=false

- Python (openapi-generator):
  svc-infra sdk py openapi.json --outdir sdk-py --package-name client_sdk --dry-run=false

- Postman collection:
  svc-infra sdk postman openapi.json --out postman.json --dry-run=false

## Quick curl examples

Replace URL and payload as needed; these align with x-codeSamples included in the schema.

- GET
  curl -X GET 'http://localhost:8000/v1/projects'

- POST with JSON
  curl -X POST 'http://localhost:8000/v1/projects' \
    -H 'Content-Type: application/json' \
    -d '{"name":"Example"}'

Notes:
- You need Node.js; the CLI calls `npx` for generator tools. Add them to your devDependencies for reproducibility.
- For CI, export OpenAPI to a path and run the CLI with `--dry-run=false`.

## Troubleshooting

- Docs not visible at `/`? If your app already handles `/`, the landing page is mounted at `/_docs`.
- Dark mode not applying? Use `/docs?theme=dark` or `/redoc?theme=dark`.
- Missing Problem examples? Ensure your error handlers reference the `Problem` schema and that mutators run (they are wired by default in `setup_service_api`).
