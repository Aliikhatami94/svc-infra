from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# ---- Problem Details (RFC 7807) schema ----
PROBLEM_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "format": "uri",
            "description": "A URI reference to the error type",
        },
        "title": {"type": "string", "description": "Short, human-readable summary"},
        "status": {"type": "integer", "format": "int32", "description": "HTTP status code"},
        "detail": {"type": "string", "description": "Human-readable explanation of the error"},
        "instance": {
            "type": "string",
            "format": "uri",
            "description": "A URI reference to this occurrence",
        },
        # Enterprise-friendly extensions
        "code": {"type": "string", "description": "Stable application error code"},
        "errors": {
            "type": "array",
            "description": "Optional list of field/validation errors",
            "items": {
                "type": "object",
                "properties": {
                    "loc": {"type": "array", "items": {"type": "string"}},
                    "msg": {"type": "string"},
                    "type": {"type": "string"},
                },
            },
        },
        "trace_id": {"type": "string", "description": "Correlation/trace id (if available)"},
    },
    "required": ["title", "status"],
}

# ---- Reusable response components ----
STANDARD_RESPONSES: Dict[str, Dict[str, Any]] = {
    "Unauthorized": {
        "description": "Authentication required or failed",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    },
    "Forbidden": {
        "description": "The authenticated principal does not have access",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    },
    "NotFound": {
        "description": "The requested resource was not found",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    },
    "ValidationError": {
        "description": "Request failed validation",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    },
    "Conflict": {
        "description": "A conflicting resource already exists or constraints were violated",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    },
    "TooManyRequests": {
        "description": "Rate limit exceeded",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    },
    "ServerError": {
        "description": "Unexpected server error",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    },
}


def install_openapi_conventions(app: FastAPI) -> None:
    """
    Augment OpenAPI with:
      - Problem schema
      - Standard reusable responses (401/403/404/422/409/429/5xx)
      - (Optional) normalize empty 200s to 204 in docs if desired
    """

    def _openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        comps = schema.setdefault("components", {})
        schemas = comps.setdefault("schemas", {})
        responses = comps.setdefault("responses", {})

        # Schemas
        schemas.setdefault("Problem", PROBLEM_SCHEMA)

        # Responses
        for k, v in STANDARD_RESPONSES.items():
            responses.setdefault(k, v)

        # Optionally: convert documented empty 200 bodies to 204 (docs-only hygiene)
        for path_item in (schema.get("paths") or {}).values():
            for method_obj in list(path_item.values()):
                if not isinstance(method_obj, dict):
                    continue
                resp = method_obj.get("responses") or {}
                if "200" in resp:
                    content = resp["200"].get("content") or {}
                    # If 200 has no schema/content, prefer 204 (no body)
                    if not content:
                        resp.pop("200", None)
                        resp.setdefault("204", {"description": "No Content"})

        app.openapi_schema = schema
        return schema

    app.openapi = _openapi
