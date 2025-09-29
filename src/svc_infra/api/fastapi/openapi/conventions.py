from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

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
        "instance": {"type": "string", "format": "uri", "description": "URI for this occurrence"},
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


STANDARD_RESPONSES: Dict[str, Dict[str, Any]] = {
    "BadRequest": {
        "description": "The request is malformed or missing required fields",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
                "examples": {
                    "default": {
                        "value": _problem_example(
                            title="Bad Request",
                            status=400,
                            detail="Invalid request payload.",
                            code="BAD_REQUEST",
                        )
                    }
                },
            }
        },
    },
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
                "examples": {"default": {"value": _problem_example()}},
            }
        },
    },
}


def install_openapi_conventions(app: FastAPI) -> None:
    previous = getattr(app, "openapi", None)

    def _openapi():
        base_schema = (
            previous()
            if callable(previous)
            else get_openapi(title=app.title, version=app.version, routes=app.routes)
        )
        schema = dict(base_schema)

        comps = schema.setdefault("components", {})
        schemas = comps.setdefault("schemas", {})
        responses = comps.setdefault("responses", {})

        # Respect existing info / servers – only set defaults if missing
        info = schema.setdefault("info", {})
        info.setdefault("contact", {"name": "API Support", "email": "support@example.com"})
        info.setdefault("license", {"name": "Apache-2.0"})
        schema.setdefault("servers", [{"url": "/"}])

        # Problem schema + reusable responses
        schemas.setdefault("Problem", PROBLEM_SCHEMA)
        for k, v in STANDARD_RESPONSES.items():
            responses.setdefault(k, v)

        # (optional) normalize no-$ref-siblings, 200→204, etc… if you still want those

        app.openapi_schema = schema
        return schema

    app.openapi = _openapi
