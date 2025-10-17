# Pre-Deploy Acceptance (Promotion Gate)

This guide describes the acceptance harness that runs post-build against an ephemeral stack. Artifacts are promoted only if acceptance checks pass.

## Stack
- docker-compose.test.yml: api (image from CI), db, redis
- Makefile targets: accept, compose_up, wait, seed, down
- Health probes: /healthz (liveness), /readyz (readiness), /startupz (startup)

## Workflow
1. Build image
2. docker compose up -d (test stack)
3. Seed acceptance data (admin, user, tenants, API key)
4. pytest -m "acceptance or smoke" -q
5. OpenAPI lint & API Doctor
6. Teardown

## Supply-chain & Matrix (v1 scope)
- SBOM: generate and upload as artifact; image scan (Trivy/Grype) with severity gate.
- Provenance: sign/attest images (cosign/SLSA) on best-effort basis.
- Backend matrix: run acceptance against two stacks:
	1) in-memory stores, 2) Redis + Postgres.

## Additional Acceptance Checks (fast wins)
- Headers/CORS: assert HSTS, X-Content-Type-Options, Referrer-Policy, X-Frame-Options/SameSite; OPTIONS preflight behavior.
- Resilience: restart DB/Redis during request; expect breaker trip and recovery.
- DR drill: restore a tiny SQL dump then run smoke.
- OpenAPI invariants: no orphan routes; servers block correctness for versions; 100% examples for public JSON; stable operationIds; reject /auth/{id} path via lint rule.
- CLI contracts: `svc-infra --help` and key subcommands exit 0 and print expected flags.

## Local usage
- make accept (runs the full flow locally)
- pytest -m acceptance (against a running local stack) with BASE_URL=http://localhost:8000

## Files
- tests/acceptance/conftest.py: BASE_URL, httpx client, fixtures
- tests/acceptance/_auth.py: login/register helpers
- tests/acceptance/_seed.py: seed users/tenants/api keys
- tests/acceptance/_http.py: HTTP helpers

## Scenarios
See docs/acceptance-matrix.md for A-IDs and mapping to endpoints.
