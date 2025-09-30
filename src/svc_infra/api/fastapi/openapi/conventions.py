from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI

from .mutators import conventions_mutator
from .pipeline import apply_mutators

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
            "format": "uri-reference",
            "description": "URI reference for this occurrence",
        },
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
        "instance": "https://api.example.com/request/abc123",
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
    apply_mutators(app, conventions_mutator())
