from __future__ import annotations

from typing import Dict


# Shorthand to reference components.responses
def ref(name: str) -> dict:
    return {"$ref": f"#/components/responses/{name}"}


# Common bundles (use as defaults per router)
DEFAULT_PUBLIC: Dict[int, dict] = {
    422: ref("ValidationError"),
    500: ref("ServerError"),
}
DEFAULT_USER: Dict[int, dict] = {
    401: ref("Unauthorized"),
    403: ref("Forbidden"),
    422: ref("ValidationError"),
    500: ref("ServerError"),
}
DEFAULT_SERVICE: Dict[int, dict] = {
    401: ref("Unauthorized"),
    403: ref("Forbidden"),
    429: ref("TooManyRequests"),
    500: ref("ServerError"),
}
DEFAULT_PROTECTED: Dict[int, dict] = {
    401: ref("Unauthorized"),
    403: ref("Forbidden"),
    422: ref("ValidationError"),
    500: ref("ServerError"),
}

# Handy named ones for endpoints to add as-needed
UNAUTHORIZED = ref("Unauthorized")
FORBIDDEN = ref("Forbidden")
NOT_FOUND = ref("NotFound")
VALIDATION_ERROR = ref("ValidationError")
CONFLICT = ref("Conflict")
TOO_MANY = ref("TooManyRequests")
SERVER_ERROR = ref("ServerError")


def merge_responses(
    base: Dict[int, dict] | None, *extras: dict, **by_code: dict
) -> Dict[int, dict]:
    """
    Merge a base responses dict with any number of $ref dicts and/or code->ref mappings.
    Example:
        merge_responses(DEFAULT_USER, NOT_FOUND, CONFLICT, **{409: CONFLICT})
    """
    out: Dict[int, dict] = {}
    if base:
        out.update(base)
    for extra in extras:
        # try to infer a code from common names when not provided explicitly
        # (but generally you’ll pass by_code for custom codes)
        pass
    for code, resp in by_code.items():
        out[int(code)] = resp
    return out
