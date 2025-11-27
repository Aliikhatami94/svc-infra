# Pre-Deploy Acceptance (Promotion Gate)

This guide describes the acceptance harness that runs post-build against an ephemeral stack. Artifacts are promoted only if acceptance checks pass.

## Stack
- docker-compose.test.yml: api (uvicorn serving tests.acceptance.app), optional db/redis (via profiles), and a tester container to run pytest inside
- Makefile targets: accept, compose_up, wait, seed, down
- Health probes: /healthz (liveness), /readyz (readiness), /startupz (startup)

## Workflow
1. Build image
2. docker compose up -d (test stack)
3. CLI DB checks & seed: run `sql setup-and-migrate`, `sql current`, `sql downgrade -1`, `sql upgrade head` against an ephemeral SQLite DB, then call `sql seed tests.acceptance._seed:acceptance_seed` (no-op by default)
4. Run pytest inside tester: docker compose run --rm tester (Makefile wires this)
5. OpenAPI lint & API Doctor
6. Teardown

## Supply-chain & Matrix (v1 scope)
- SBOM: generate and upload as artifact; image scan (Trivy/Grype) with severity gate.
- Provenance: sign/attest images (cosign/SLSA) on best-effort basis.
- Backend matrix: run acceptance against two stacks via COMPOSE_PROFILES:
	1) in-memory stores (default), 2) Redis + Postgres (COMPOSE_PROFILES=pg-redis).

## Additional Acceptance Checks (fast wins)
- Headers/CORS: assert HSTS, X-Content-Type-Options, Referrer-Policy, X-Frame-Options/SameSite; OPTIONS preflight behavior.
- Resilience: restart DB/Redis during request; expect breaker trip and recovery.
- DR drill: restore a tiny SQL dump then run smoke.
- OpenAPI invariants: no orphan routes; servers block correctness for versions; 100% examples for public JSON; stable operationIds; reject /auth/{id} path via lint rule.
- CLI contracts: `svc-infra --help` and key subcommands exit 0 and print expected flags.

## Local usage
- make accept (runs the full flow locally)
- make down (tears down the stack)
- To run tests manually: docker compose run --rm tester
- To target a different backend: COMPOSE_PROFILES=pg-redis make accept

## Files
- tests/acceptance/conftest.py: BASE_URL, httpx client, fixtures
- tests/acceptance/_auth.py: login/register helpers
- tests/acceptance/_seed.py: seed users/tenants/api keys
- tests/acceptance/_http.py: HTTP helpers

## Scenarios
See docs/acceptance-matrix.md for A-IDs and mapping to endpoints.
