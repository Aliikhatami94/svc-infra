from __future__ import annotations

import json
from pathlib import Path

import pytest

from svc_infra.dx.changelog import Commit, generate_release_section
from svc_infra.dx.checks import check_migrations_up_to_date, check_openapi_problem_schema

pytestmark = pytest.mark.dx


def _minimal_openapi_with_problem() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "x", "version": "1"},
        "paths": {},
        "components": {
            "schemas": {
                "Problem": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "format": "uri"},
                        "title": {"type": "string"},
                        "status": {"type": "integer"},
                        "detail": {"type": "string"},
                        "instance": {"type": "string", "format": "uri-reference"},
                        "code": {"type": "string"},
                    },
                }
            }
        },
    }


def test_check_openapi_problem_schema_passes(tmp_path: Path):
    p = tmp_path / "openapi.json"
    p.write_text(json.dumps(_minimal_openapi_with_problem()))
    check_openapi_problem_schema(path=p)


def test_check_openapi_problem_schema_fails_on_missing(tmp_path: Path):
    p = tmp_path / "openapi.json"
    p.write_text(json.dumps({"openapi": "3.1.0", "info": {"title": "x", "version": "1"}}))
    with pytest.raises(ValueError):
        check_openapi_problem_schema(path=p)


def test_check_migrations_up_to_date_tolerates_absence(tmp_path: Path):
    # no alembic.ini -> no-op
    check_migrations_up_to_date(project_root=tmp_path)


def test_check_migrations_up_to_date_requires_versions_when_alembic_present(tmp_path: Path):
    (tmp_path / "alembic.ini").write_text("[alembic]")
    (tmp_path / "migrations").mkdir()
    with pytest.raises(ValueError):
        check_migrations_up_to_date(project_root=tmp_path)


def test_generate_release_section_groups_commits():
    commits = [
        Commit(sha="a1b2c3", subject="feat: new endpoint"),
        Commit(sha="d4e5f6", subject="fix: 500 on /foo"),
        Commit(sha="112233", subject="refactor: cleanup"),
        Commit(sha="445566", subject="docs: update readme"),
    ]
    out = generate_release_section(version="0.1.604", commits=commits, release_date="2025-10-16")
    assert "## v0.1.604 - 2025-10-16" in out
    assert "### Features" in out and "new endpoint" in out
    assert "### Bug Fixes" in out and "500 on /foo" in out
    assert "### Refactors" in out and "cleanup" in out
    assert "### Other" in out and "update readme" in out
