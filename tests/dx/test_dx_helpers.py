from __future__ import annotations

from pathlib import Path

from svc_infra.dx.add import write_ci_workflow, write_openapi_lint_config


def test_dx_writers(tmp_path: Path):
    p = write_ci_workflow(target_dir=tmp_path)
    assert p.exists()
    assert "actions/checkout" in p.read_text()

    q = write_openapi_lint_config(target_dir=tmp_path)
    assert q.exists()
    content = q.read_text()
    assert "apis:" in content and "rules:" in content
