# Contributing

Thanks for considering a contribution! This repo aims to provide production-ready primitives with clear gates.

## Local setup

- Python 3.11–3.13
- Install via Poetry:
  - `poetry install`
  - `poetry run pre-commit install`

## Quality gates (run before PR)

- Lint: `poetry run flake8 --select=E,F`
- Typecheck: `poetry run mypy src`
- Tests: `poetry run pytest -q -W error`
- OpenAPI lint (optional): `poetry run python -m svc_infra.cli dx openapi openapi.json`
- Migrations present (optional): `poetry run python -m svc_infra.cli dx migrations --project-root .`
- CI dry-run (optional): `poetry run python -m svc_infra.cli dx ci --openapi openapi.json`

## Commit style

- Prefer Conventional Commits: `feat:`, `fix:`, `refactor:`, etc.
- Use changelog generator for releases:
  - `poetry run python -m svc_infra.cli dx changelog 0.1.604 --commits-file commits.jsonl`

## Release process

1. Ensure all gates are green locally (see above).
2. Update version in `pyproject.toml`.
3. Export OpenAPI (if applicable) via docs helper.
4. Generate changelog section and review.
5. Merge to `main`. CI will run tests, lint, and typecheck.
6. Tag and publish.
