from __future__ import annotations

from pathlib import Path


def write_ci_workflow(
    *,
    target_dir: str | Path,
    name: str = "ci.yml",
    python_version: str = "3.12",
) -> Path:
    """Write a minimal CI workflow file (GitHub Actions) with tests/lint/type steps."""
    p = Path(target_dir) / ".github" / "workflows" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    content = f"""
name: CI

on:
  push:
    branches: [ main ]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '{python_version}'
      - name: Install Poetry
        run: pipx install poetry
      - name: Install deps
        run: poetry install
      - name: Lint
        run: poetry run flake8 --select=E,F
      - name: Typecheck
        run: poetry run mypy src
      - name: Tests
        run: poetry run pytest -q -W error
"""
    p.write_text(content.strip() + "\n")
    return p


def write_openapi_lint_config(*, target_dir: str | Path, name: str = ".redocly.yaml") -> Path:
    """Write a minimal OpenAPI lint config placeholder (Redocly)."""
    p = Path(target_dir) / name
    content = """
apis:
  main:
    root: openapi.json

rules:
  operation-operationId: warn
  no-unused-components: warn
  security-defined: off
"""
    p.write_text(content.strip() + "\n")
    return p


__all__ = ["write_ci_workflow", "write_openapi_lint_config"]
