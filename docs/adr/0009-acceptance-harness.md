# ADR 0009: Acceptance Harness & Promotion Gate (A0)

Date: 2025-10-17
Status: Proposed
Decision: Adopt a post-build acceptance harness that brings up an ephemeral stack (Docker Compose) and gates image promotion on acceptance results.

## Context
- We need a thin but strict pre-deploy acceptance layer that runs after building images, before promotion.
- It should validate golden paths across domains and basic operational invariants.
- It must be easy to run locally and in CI and support a backend matrix (in-memory vs Redis+Postgres).
- Supply-chain checks (SBOM, image scan, provenance) should be part of the gate.

## Decision
- Introduce A0 Acceptance Harness:
  - Compose stack (api + db + redis), Makefile helpers (accept/up/wait/seed/down).
  - Seed CLI/script to create ADMIN/USER/TENANT fixtures and API key.
  - Acceptance tests under `tests/acceptance` with `@pytest.mark.acceptance` and BASE_URL.
  - CI job `build-and-accept` steps: build → compose up → seed → `pytest -m "acceptance or smoke"` → OpenAPI lint + API Doctor → teardown.
  - Supply-chain: generate SBOM, image scan (Trivy/Grype) with severity threshold; upload SBOM.
  - Provenance: sign/attest images via cosign/SLSA (best-effort for v1).
  - Backend matrix: two jobs (in-memory vs Redis+Postgres).

## Alternatives
- Testcontainers-only approach (simpler per-test spin-up) — good DX but slower; we can adopt later for certain suites.
- Kubernetes-in-Docker (kind) for near-prod parity — heavier; likely a v2 improvement.

## Consequences
- Slightly longer CI time due to matrix and scans.
- Clearer promotion safety; early detection of config/env gaps.

## Implementation Notes
- Files to add:
  - `docker-compose.test.yml`
  - `Makefile` targets: `accept`, `compose_up`, `wait`, `seed`, `down`
  - `tests/acceptance/` scaffolding: `conftest.py`, `_seed.py`, `_auth.py`, `_http.py`, first tests (headers/CORS)
  - CI: `.github/workflows/ci.yml` job `build-and-accept`
- Env contracts:
  - `SQL_URL`, `REDIS_URL` for backend matrix; `APP_ENV=test-accept` for toggles.
- Evidence:
  - CI run URL, SBOM artifact link, scan report, acceptance summary.
