# Developer Experience (DX) Guide

Utilities for CI/CD workflows, changelog generation, and code quality checks.

## Overview

The svc-infra dx module provides tools to improve developer experience:

- **CI Workflow Generation**: Generate GitHub Actions workflows
- **Changelog Generation**: Generate release notes from conventional commits
- **Code Quality Checks**: OpenAPI schema validation and migration verification

## Quick Start

### Generate CI Workflow

```python
from svc_infra.dx import write_ci_workflow

# Generate GitHub Actions workflow
path = write_ci_workflow(target_dir="./myproject", python_version="3.12")
print(f"Created: {path}")  # ./myproject/.github/workflows/ci.yml
```

### Generate Changelog Section

```python
from svc_infra.dx import Commit, generate_release_section

commits = [
    Commit(sha="abc1234", subject="feat: add user authentication"),
    Commit(sha="def5678", subject="fix: resolve login timeout"),
    Commit(sha="ghi9012", subject="perf: optimize database queries"),
]

changelog = generate_release_section(version="1.2.0", commits=commits)
print(changelog)
```

Output:

```markdown
## v1.2.0 - 2024-01-15

### Features
- add user authentication (abc1234)

### Bug Fixes
- resolve login timeout (def5678)

### Performance
- optimize database queries (ghi9012)
```

### Validate OpenAPI Schema

```python
from svc_infra.dx import check_openapi_problem_schema

# Validate from file
check_openapi_problem_schema(path="openapi.json")

# Or validate from dict
check_openapi_problem_schema(schema=openapi_dict)
```

---

## CI Workflow Generation

### write_ci_workflow

Generate a GitHub Actions CI workflow with tests, linting, and type checking.

```python
from svc_infra.dx import write_ci_workflow

# Basic usage
write_ci_workflow(target_dir=".")

# With custom Python version
write_ci_workflow(
    target_dir="./myproject",
    python_version="3.11",
    name="test.yml",  # Custom filename
)
```

#### Generated Workflow

```yaml
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
          python-version: '3.12'
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
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_dir` | `str \| Path` | Required | Project root directory |
| `name` | `str` | `"ci.yml"` | Workflow filename |
| `python_version` | `str` | `"3.12"` | Python version for setup |

---

## OpenAPI Lint Config

### write_openapi_lint_config

Generate a Redocly OpenAPI linting configuration.

```python
from svc_infra.dx import write_openapi_lint_config

write_openapi_lint_config(target_dir="./myproject")
```

#### Generated Config (.redocly.yaml)

```yaml
apis:
  main:
    root: openapi.json

rules:
  operation-operationId: warn
  no-unused-components: warn
  security-defined: off
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_dir` | `str \| Path` | Required | Project root directory |
| `name` | `str` | `".redocly.yaml"` | Config filename |

---

## Changelog Generation

### Commit Dataclass

Represents a git commit for changelog generation.

```python
from svc_infra.dx import Commit

commit = Commit(
    sha="abc1234",
    subject="feat(auth): add OAuth2 support"
)
```

### generate_release_section

Generate a markdown release section from conventional commits.

```python
from svc_infra.dx import Commit, generate_release_section

commits = [
    Commit(sha="a1b2c3d", subject="feat: add new feature"),
    Commit(sha="e4f5g6h", subject="feat(api): add user endpoints"),
    Commit(sha="i7j8k9l", subject="fix: resolve crash on startup"),
    Commit(sha="m0n1o2p", subject="fix(auth): fix token expiration"),
    Commit(sha="q3r4s5t", subject="perf: optimize database queries"),
    Commit(sha="u6v7w8x", subject="refactor: clean up code"),
    Commit(sha="y9z0a1b", subject="docs: update README"),
]

changelog = generate_release_section(
    version="2.0.0",
    commits=commits,
    release_date="2024-01-15",  # Optional, defaults to today
)

print(changelog)
```

#### Output

```markdown
## v2.0.0 - 2024-01-15

### Features
- add new feature (a1b2c3d)
- add user endpoints (e4f5g6h)

### Bug Fixes
- resolve crash on startup (i7j8k9l)
- fix token expiration (m0n1o2p)

### Performance
- optimize database queries (q3r4s5t)

### Refactors
- clean up code (u6v7w8x)

### Other
- update README (y9z0a1b)
```

#### Commit Type Classification

| Prefix | Section |
|--------|---------|
| `feat:` or `feat(scope):` | Features |
| `fix:` or `fix(scope):` | Bug Fixes |
| `perf:` or `perf(scope):` | Performance |
| `refactor:` or `refactor(scope):` | Refactors |
| Everything else | Other |

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `version` | `str` | Required | Version number (without 'v' prefix) |
| `commits` | `Sequence[Commit]` | Required | List of commits |
| `release_date` | `str \| None` | Today's date | ISO date string |

---

## Code Quality Checks

### check_openapi_problem_schema

Validate that your OpenAPI schema includes a proper Problem schema (RFC 7807).

```python
from svc_infra.dx import check_openapi_problem_schema

# From file
try:
    check_openapi_problem_schema(path="openapi.json")
    print("OpenAPI schema valid!")
except ValueError as e:
    print(f"Validation failed: {e}")

# From dict
schema = {
    "components": {
        "schemas": {
            "Problem": {
                "properties": {
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {"type": "integer"},
                    "detail": {"type": "string"},
                    "instance": {"type": "string", "format": "uri-reference"},
                    "code": {"type": "string"},
                }
            }
        }
    }
}
check_openapi_problem_schema(schema=schema)
```

#### Required Problem Schema Fields

| Field | Requirement |
|-------|-------------|
| `type` | Must be present |
| `title` | Must be present |
| `status` | Must be present |
| `detail` | Must be present |
| `instance` | Must be present with `format: uri-reference` |
| `code` | Must be present |

### check_migrations_up_to_date

Verify Alembic migrations directory structure is correct.

```python
from svc_infra.dx import check_migrations_up_to_date

try:
    check_migrations_up_to_date(project_root="./myproject")
    print("Migrations structure OK!")
except ValueError as e:
    print(f"Migrations issue: {e}")
```

#### Checks Performed

1. If `alembic.ini` exists:
   - Verifies `migrations/` directory exists
   - Verifies `migrations/versions/` subdirectory exists

---

## CLI Integration

The dx module also provides CLI commands via `svc-infra`:

```bash
# Generate CI workflow
svc-infra dx ci --target-dir ./myproject

# Validate OpenAPI schema
svc-infra dx openapi --path openapi.json

# Generate changelog
svc-infra dx changelog --version 1.0.0
```

---

## Pre-commit Hook Example

Use dx utilities in pre-commit hooks:

```python
#!/usr/bin/env python3
"""Pre-commit hook for OpenAPI validation."""

import sys
from pathlib import Path
from svc_infra.dx import check_openapi_problem_schema

openapi_path = Path("openapi.json")

if openapi_path.exists():
    try:
        check_openapi_problem_schema(path=openapi_path)
        print("✓ OpenAPI Problem schema valid")
    except ValueError as e:
        print(f"✗ OpenAPI validation failed: {e}")
        sys.exit(1)
```

---

## Full Example

```python
from pathlib import Path
from svc_infra.dx import (
    write_ci_workflow,
    write_openapi_lint_config,
    Commit,
    generate_release_section,
    check_openapi_problem_schema,
    check_migrations_up_to_date,
)

project_dir = Path("./myproject")

# Setup CI/CD
write_ci_workflow(target_dir=project_dir, python_version="3.12")
write_openapi_lint_config(target_dir=project_dir)

# Validate project
check_migrations_up_to_date(project_root=project_dir)
check_openapi_problem_schema(path=project_dir / "openapi.json")

# Generate changelog for release
commits = [
    Commit(sha="abc1234", subject="feat: add new feature"),
    Commit(sha="def5678", subject="fix: resolve bug"),
]

changelog = generate_release_section(version="1.0.0", commits=commits)

# Prepend to CHANGELOG.md
changelog_path = project_dir / "CHANGELOG.md"
existing = changelog_path.read_text() if changelog_path.exists() else ""
changelog_path.write_text(changelog + "\n" + existing)

print("Release prepared!")
```

---

## API Reference

### CI/CD Functions

| Function | Description |
|----------|-------------|
| `write_ci_workflow(...)` | Generate GitHub Actions CI workflow |
| `write_openapi_lint_config(...)` | Generate Redocly OpenAPI lint config |

### Changelog Functions

| Function | Description |
|----------|-------------|
| `generate_release_section(...)` | Generate markdown release section |

### Check Functions

| Function | Description |
|----------|-------------|
| `check_openapi_problem_schema(...)` | Validate OpenAPI Problem schema |
| `check_migrations_up_to_date(...)` | Verify Alembic migrations structure |

### Classes

| Class | Description |
|-------|-------------|
| `Commit` | Dataclass for commit representation (sha, subject) |
