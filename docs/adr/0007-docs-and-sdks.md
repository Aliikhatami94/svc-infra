# ADR 0007: Docs & SDKs — Research and Design

Status: Proposed

Date: 2025-10-16

## Context

We want a production-ready documentation and SDK experience built on our existing FastAPI scaffolding.
Current capabilities in the codebase:

- Docs endpoints and export
  - `add_docs(app, redoc_url, swagger_url, openapi_url, export_openapi_to)` mounts Swagger, ReDoc, and OpenAPI JSON; optional export on startup.
  - `setup_service_api(...)` renders a landing page with per-version doc cards and local-only root docs.
  - `add_prefixed_docs(...)` exposes scoped docs (e.g., for auth/payments) with per-scope OpenAPI, Swagger, ReDoc.
- OpenAPI conventions and enrichment pipeline
  - Mutators pipeline (`openapi/mutators.py`) with: conventions, normalized Problem schema, pagination params/components, header params, info mutator, and auth scheme installers.
  - Conventions define `Problem` schema and normalize examples.
- DX checks
  - OpenAPI Problem+JSON lint in `dx/checks.py` and CLI to validate.
- SDK stub
  - `add_sdk_generation_stub(app, on_generate=...)` exposes a hook endpoint to trigger SDK generation (no hard deps).

Gaps for a complete v1 experience:

- Enriched OpenAPI with examples and tags is not yet standardized across routers.
- No built-in SDK generator CLI; only a stub exists. No pinned toolchain or CI integration.
- No Postman collection generator.
- No dark-mode toggle/themes for Swagger/ReDoc (landing page supports light/dark).
- No smoke tests for generated SDKs.

## Decision

We will standardize the Docs & SDKs approach around the following:

1) OpenAPI enrichment
- Use existing mutators pipeline and add small mutators to:
  - Inject global tags and tag descriptions for major areas (auth, payments, webhooks, ops).
  - Attach minimal `x-codeSamples` for common operations (curl/httpie).
  - Ensure `Problem` schema and example responses are present across 4xx/5xx.
  - Keep pagination and header parameter mutators enabled by default.

2) Docs UI
- Continue with Swagger UI and ReDoc via `add_docs` and `setup_service_api`.
- Add an optional dark mode toggle for Swagger UI via custom CSS and a query param (design-only; implement later).
- Keep local-only exposure of root docs; version-specific docs always exposed under their mount path.

3) SDK generation pipeline (tools and layout)
- TypeScript: `openapi-typescript` to generate types (no runtime client) to `clients/typescript/`.
- Python: `openapi-python-client` to generate a client package to `clients/python/`.
- Provide a new CLI group `svc-infra sdk` with subcommands:
  - `svc-infra sdk ts --schema openapi.json --out clients/typescript --package @org/service`
  - `svc-infra sdk py --schema openapi.json --out clients/python --package service_sdk`
  - `svc-infra sdk postman --schema openapi.json --out clients/postman_collection.json` (via converter)
- Pin generator versions in a minimal tool manifest (poetry extras and npm devDeps suggestions in docs) rather than hard deps in core library.
- Add optional CI steps to generate SDKs on release tags; artifacts uploaded; publishing pipelines documented.

4) Postman collection
- Use the Postman converter (`openapi-to-postmanv2`) to produce `clients/postman_collection.json` from the exported OpenAPI.

5) Testing & verification
- Extend `dx` checks to include: schema export presence, generator dry-run, and minimal smoke tests:
  - TS: typecheck the generated d.ts.
  - Python: `pip install -e` and import a sample client in a quick script.
- Keep these checks optional (opt-in via CI config) to avoid burdening minimal users.

## Consequences

- Pros: Clear, tool-agnostic pipeline; no heavy runtime dependencies; easy local and CI usage; versioned artifacts.
- Cons: Adds extra tooling expectations (node and python generators) for teams that opt in.
- Risk: Generator/tooling churn; mitigate by pinning versions and providing stubs/fallbacks.

## Implementation Notes (planned)

- Provide a small `svc_infra/cli/cmds/sdk` module with Typer commands that shell out to the generators if available, with helpful error messages if missing.
- Document usage in `docs/docs-and-sdks.md` (to be added), including examples and troubleshooting.
- Keep all new code behind DX/CLI; core library remains free of generator dependencies.

## Out of Scope (v1)

- Live “try it” consoles beyond Swagger UI.
- Multi-language example snippets beyond curl/httpie.
- Automatic publishing to npm/PyPI (documented manual workflows first).
