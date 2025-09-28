from __future__ import annotations

from typing import Dict


def ref(name: str) -> dict:
    return {"$ref": f"#/components/responses/{name}"}


DEFAULT_PUBLIC: Dict[int, dict] = {
    400: ref("BadRequest"),
    422: ref("ValidationError"),
    500: ref("ServerError"),
}
DEFAULT_USER: Dict[int, dict] = {
    400: ref("BadRequest"),
    401: ref("Unauthorized"),
    403: ref("Forbidden"),
    422: ref("ValidationError"),
    500: ref("ServerError"),
}
DEFAULT_SERVICE: Dict[int, dict] = {
    400: ref("BadRequest"),
    401: ref("Unauthorized"),
    403: ref("Forbidden"),
    429: ref("TooManyRequests"),
    500: ref("ServerError"),
}
DEFAULT_PROTECTED: Dict[int, dict] = {
    400: ref("BadRequest"),
    401: ref("Unauthorized"),
    403: ref("Forbidden"),
    422: ref("ValidationError"),
    500: ref("ServerError"),
}

BAD_REQUEST = ref("BadRequest")
UNAUTHORIZED = ref("Unauthorized")
FORBIDDEN = ref("Forbidden")
NOT_FOUND = ref("NotFound")
VALIDATION_ERROR = ref("ValidationError")
CONFLICT = ref("Conflict")
TOO_MANY = ref("TooManyRequests")
SERVER_ERROR = ref("ServerError")
