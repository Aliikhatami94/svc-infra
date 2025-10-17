from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.docs.add import add_docs


@pytest.mark.docs
def test_add_docs_and_export(tmp_path: Path):
    app = FastAPI()
    out = tmp_path / "openapi.json"
    add_docs(
        app,
        swagger_url="/swagger",
        redoc_url="/redocx",
        openapi_url="/spec.json",
        export_openapi_to=str(out),
    )

    with TestClient(app) as client:
        # Docs endpoints present
        assert client.get("/swagger").status_code in {200, 307, 308}
        assert client.get("/redocx").status_code in {200, 307, 308}
        assert client.get("/spec.json").status_code == 200

    # Exported file exists
    assert out.exists()
    assert out.read_text().strip().startswith("{")


@pytest.mark.docs
def test_docs_dark_mode_query_param():
    app = FastAPI()
    add_docs(app, swagger_url="/swagger", redoc_url="/redocx", openapi_url="/spec.json")

    with TestClient(app) as client:
        r1 = client.get("/swagger?theme=dark")
        r2 = client.get("/redocx?theme=dark")
        assert r1.status_code in {200, 307, 308}
        # Follow redirect for swagger if any
        if r1.is_redirect:
            r1 = client.get(r1.headers["location"])  # type: ignore[index]
        assert "<style" in r1.text or 'class="dark"' in r1.text

        assert r2.status_code in {200, 307, 308}
        if r2.is_redirect:
            r2 = client.get(r2.headers["location"])  # type: ignore[index]
        assert "<style" in r2.text or 'class="dark"' in r2.text
