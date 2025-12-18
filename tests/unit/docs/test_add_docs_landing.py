from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.docs.add import add_docs


@pytest.mark.docs
def test_add_docs_renders_landing_at_root():
    app = FastAPI(title="Demo", version="0.1.0")
    add_docs(app, swagger_url="/swagger", redoc_url="/redocx", openapi_url="/spec.json")

    with TestClient(app) as client:
        # landing should be at '/'
        r = client.get("/")
        assert r.status_code == 200
        body = r.text
        assert "/swagger" in body
        assert "/redocx" in body
        assert "/spec.json" in body


@pytest.mark.docs
def test_add_docs_landing_falls_back_when_root_taken():
    app = FastAPI(title="Demo", version="0.1.0")

    @app.get("/")
    def hello():
        return {"ok": True}

    add_docs(app, swagger_url="/swagger", redoc_url="/redocx", openapi_url="/spec.json")

    with TestClient(app) as client:
        # root remains original route
        assert client.get("/").status_code == 200
        # landing should be available under fallback path '/_docs'
        r = client.get("/_docs")
        assert r.status_code == 200
        body = r.text
        assert "/swagger" in body
        assert "/redocx" in body
        assert "/spec.json" in body
