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
            "description": "URI identifying the error type",
        },
        "title": {"type": "string", "description": "Short, human-readable summary"},
        "status": {"type": "integer", "format": "int32", "description": "HTTP status code"},
        "detail": {"type": "string", "description": "Human-readable explanation"},
        "instance": {
            "type": "string",
            "format": "uri",
            "description": "URI identifying this occurrence",
        },
        # Extensions commonly requested by enterprises:
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


def _problem_example(**kw: Any) -> Dict[str, Any]:
    base = {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "Something went wrong. Please contact support.",
        "instance": "/request/abc123",
        "code": "INTERNAL_ERROR",
        "trace_id": "00000000000000000000000000000000",
    }
    base.update(kw)
    return base


# ---- Reusable response components (with examples) ----
STANDARD_RESPONSES: Dict[str, Dict[str, Any]] = {
    "Unauthorized": {
        "description": "Authentication required or failed",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
                "examples": {
                    "default": {
                        "value": _problem_example(
                            title="Unauthorized",
                            status=401,
                            detail="Missing or invalid credentials.",
                            code="UNAUTHORIZED",
                        )
                    }
                },
            }
        },
    },
    "Forbidden": {
        "description": "The authenticated principal does not have access",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
                "examples": {
                    "default": {
                        "value": _problem_example(
                            title="Forbidden",
                            status=403,
                            detail="You do not have permission to perform this action.",
                            code="FORBIDDEN",
                        )
                    }
                },
            }
        },
    },
    "NotFound": {
        "description": "The requested resource was not found",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
                "examples": {
                    "default": {
                        "value": _problem_example(
                            title="Not Found",
                            status=404,
                            detail="Resource not found.",
                            code="NOT_FOUND",
                        )
                    }
                },
            }
        },
    },
    "ValidationError": {
        "description": "Request failed validation",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
                "examples": {
                    "default": {
                        "value": _problem_example(
                            title="Unprocessable Entity",
                            status=422,
                            detail="Validation failed.",
                            code="VALIDATION_ERROR",
                            errors=[
                                {
                                    "loc": ["body", "email"],
                                    "msg": "value is not a valid email address",
                                    "type": "value_error.email",
                                }
                            ],
                        )
                    }
                },
            }
        },
    },
    "Conflict": {
        "description": "A conflicting resource already exists or constraints were violated",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
                "examples": {
                    "default": {
                        "value": _problem_example(
                            title="Conflict",
                            status=409,
                            detail="Record already exists.",
                            code="CONFLICT",
                        )
                    }
                },
            }
        },
    },
    "TooManyRequests": {
        "description": "Rate limit exceeded",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
                "examples": {
                    "default": {
                        "value": _problem_example(
                            title="Too Many Requests",
                            status=429,
                            detail="Rate limit exceeded. Try again later.",
                            code="RATE_LIMITED",
                        )
                    }
                },
            }
        },
    },
    "ServerError": {
        "description": "Unexpected server error",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
                "examples": {
                    "default": {"value": _problem_example()},
                },
            }
        },
    },
}


def install_openapi_conventions(app: FastAPI) -> None:
    """
    Augment OpenAPI with:
      - Problem schema
      - Standard reusable responses (401/403/404/422/409/429/5xx) with examples
      - Convert empty 200s to 204 for docs hygiene
    """
    previous = getattr(app, "openapi", None)

    def _strip_ref_siblings(obj: dict) -> dict:
        # If an object has a $ref, remove any sibling keys (Spectral: no-$ref-siblings)
        if isinstance(obj, dict) and "$ref" in obj:
            return {"$ref": obj["$ref"]}
        return obj

    def _is_effectively_empty_schema(s: dict | None) -> bool:
        if not isinstance(s, dict):
            return False
        # Treat {} or {"type":"object"} (with no properties) as “empty”
        if s == {}:
            return True
        if s.get("type") == "object" and not s.get("properties"):
            return True
        return False

    def _openapi():
        # Chain any prior openapi() customizer so we don't clobber other installers.
        base_schema = (
            previous()
            if callable(previous)
            else get_openapi(title=app.title, version=app.version, routes=app.routes)
        )

        schema = dict(base_schema)  # shallow copy
        comps = schema.setdefault("components", {})
        schemas = comps.setdefault("schemas", {})
        responses = comps.setdefault("responses", {})

        # Schemas
        schemas.setdefault("Problem", PROBLEM_SCHEMA)

        # Responses (with examples)
        for k, v in STANDARD_RESPONSES.items():
            responses.setdefault(k, v)

        # Empty 200 -> 204
        for path_item in (schema.get("paths") or {}).values():
            for method_obj in list(path_item.values()):
                if not isinstance(method_obj, dict):
                    continue
                resp = method_obj.get("responses") or {}
                if "200" in resp:
                    content = resp["200"].get("content") or {}
                    if not content:
                        resp.pop("200", None)
                        resp.setdefault("204", {"description": "No Content"})

        # --- Enforce no-$ref-siblings on operation responses ---
        for path_item in (schema.get("paths") or {}).values():
            for method_obj in list(path_item.values()):
                if not isinstance(method_obj, dict):
                    continue
                resp_map = method_obj.get("responses") or {}
                for code, resp in list(resp_map.items()):
                    if isinstance(resp, dict) and "$ref" in resp and len(resp) > 1:
                        resp_map[code] = {"$ref": resp["$ref"]}  # strip siblings

        # --- Upgrade "empty" 200s to 204 (also if schema was {} / root object with no props) ---
        for path_item in (schema.get("paths") or {}).values():
            for method_obj in list(path_item.values()):
                if not isinstance(method_obj, dict):
                    continue
                responses = method_obj.get("responses") or {}
                r200 = responses.get("200")
                if isinstance(r200, dict):
                    content = r200.get("content") or {}
                    # Detect “empty json” schemas and convert to 204
                    if "application/json" in content:
                        sch = content["application/json"].get("schema") or {}
                        if _is_effectively_empty_schema(sch):
                            # Prefer 204 No Content
                            responses.pop("200", None)
                            responses.setdefault("204", {"description": "No Content"})
                    # If 200 has no content at all, your existing block already converts to 204

        app.openapi_schema = schema
        return schema

    app.openapi = _openapi
