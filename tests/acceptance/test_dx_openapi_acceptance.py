from __future__ import annotations

import httpx
import pytest

from svc_infra.dx.checks import check_openapi_problem_schema


def _iter_ops(schema: dict):
    paths = schema.get("paths") or {}
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() in (
                "get",
                "put",
                "post",
                "delete",
                "options",
                "head",
                "patch",
                "trace",
            ) and isinstance(op, dict):
                yield path, method.lower(), op


@pytest.mark.acceptance
def test_a901_openapi_valid_and_examples_present(client: httpx.Client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()

    # Basic OpenAPI invariants
    assert "openapi" in data
    assert isinstance(data.get("paths"), dict)
    assert isinstance(data.get("components"), dict)
    assert isinstance(data.get("servers"), list) and data["servers"]

    # Problem schema present with expected properties
    comps = data.get("components") or {}
    prob = (comps.get("schemas") or {}).get("Problem")
    assert isinstance(prob, dict)
    props = prob.get("properties") or {}
    for key in ("type", "title", "status", "detail", "instance", "code"):
        assert key in props

    # Ensure at least one problem+json example exists and looks sane
    responses = comps.get("responses") or {}
    found_example = False
    for resp in responses.values():
        mt = isinstance(resp, dict) and (resp.get("content") or {}).get(
            "application/problem+json"
        )
        if not isinstance(mt, dict):
            continue
        examples = mt.get("examples")
        if not isinstance(examples, dict) or not examples:
            continue
        for ex in examples.values():
            if not isinstance(ex, dict):
                continue
            val = ex.get("value")
            if isinstance(val, dict):
                # minimal shape
                assert isinstance(val.get("title"), str)
                assert isinstance(val.get("status"), int)
                assert isinstance(val.get("detail"), str)
                assert isinstance(val.get("code"), str)
                assert isinstance(val.get("instance"), str)
                found_example = True
                break
        if found_example:
            break
    assert found_example, "Expected at least one application/problem+json example"


@pytest.mark.acceptance
def test_a902_problem_json_conforms(client: httpx.Client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    # Should not raise
    check_openapi_problem_schema(schema=data)


@pytest.mark.acceptance
def test_a903_openapi_simple_lints(client: httpx.Client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()

    # 1) No $ref siblings in responses (our mutator strips siblings)
    for _, _, op in _iter_ops(data):
        resps = op.get("responses") or {}
        for resp in resps.values():
            if isinstance(resp, dict) and "$ref" in resp:
                assert list(resp.keys()) == [
                    "$ref"
                ], "response $ref must not have siblings"

    # 2) application/problem+json responses should reference #/components/schemas/Problem
    comps = data.get("components") or {}
    for resp in (comps.get("responses") or {}).values():
        if not isinstance(resp, dict):
            continue
        content = resp.get("content") or {}
        prob = content.get("application/problem+json")
        if isinstance(prob, dict):
            sch = prob.get("schema")
            assert (
                isinstance(sch, dict)
                and sch.get("$ref") == "#/components/schemas/Problem"
            )
