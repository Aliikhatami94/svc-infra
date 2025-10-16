from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.docs.add import add_docs


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
