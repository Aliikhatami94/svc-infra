from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.openapi.mutators import (
    attach_code_samples_mutator,
    ensure_problem_examples_mutator,
)
from svc_infra.api.fastapi.openapi.pipeline import apply_mutators


@pytest.mark.docs
def test_openapi_has_code_samples_and_problem_examples():
    app = FastAPI()

    @app.get("/ping")
    def ping():  # noqa: D401, ANN202
        return {"ok": True}

    apply_mutators(app, attach_code_samples_mutator(), ensure_problem_examples_mutator())

    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    # Find ping operation
    op = schema["paths"]["/ping"]["get"]
    samples = op.get("x-codeSamples")
    assert isinstance(samples, list) and len(samples) >= 1

    # Error examples should be present for default errors when declared; since none
    # are declared here, mutator shouldn't break anything
    # Add a fake 500 response on the op to simulate
    schema_copy = dict(schema)
    schema_copy["paths"]["/ping"]["get"].setdefault("responses", {})["500"] = {
        "description": "err",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    }
    enriched = ensure_problem_examples_mutator()(schema_copy)
    media = enriched["paths"]["/ping"]["get"]["responses"]["500"]["content"][
        "application/problem+json"
    ]
    assert "example" in media or "examples" in media
