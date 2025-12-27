"""Developer experience utilities for CI, changelog, and code quality checks.

This module provides utilities to improve developer experience:

- **CI Workflow**: Generate GitHub Actions CI workflow files
- **Changelog**: Generate release sections from conventional commits
- **Checks**: OpenAPI schema validation and migration verification

Example:
    from svc_infra.dx import write_ci_workflow, write_openapi_lint_config

    # Generate CI workflow for a project
    write_ci_workflow(target_dir="./myproject", python_version="3.12")

    # Generate OpenAPI lint config
    write_openapi_lint_config(target_dir="./myproject")

    # Validate OpenAPI schema
    from svc_infra.dx import check_openapi_problem_schema

    check_openapi_problem_schema(path="openapi.json")

    # Generate changelog section
    from svc_infra.dx import Commit, generate_release_section

    commits = [
        Commit(sha="abc123", subject="feat: add new feature"),
        Commit(sha="def456", subject="fix: resolve bug"),
    ]
    changelog = generate_release_section(version="1.0.0", commits=commits)
    print(changelog)

See Also:
    - CLI commands: svc-infra dx openapi, svc-infra dx changelog
"""

from __future__ import annotations

# CI workflow generation
from .add import write_ci_workflow, write_openapi_lint_config

# Changelog generation
from .changelog import Commit, generate_release_section

# Code quality checks
from .checks import check_migrations_up_to_date, check_openapi_problem_schema

__all__ = [
    # CI workflow
    "write_ci_workflow",
    "write_openapi_lint_config",
    # Changelog
    "Commit",
    "generate_release_section",
    # Checks
    "check_openapi_problem_schema",
    "check_migrations_up_to_date",
]
