from __future__ import annotations

import hashlib
import hmac
import json
from typing import Dict, Iterable


def canonical_body(payload: Dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def sign(secret: str, payload: Dict) -> str:
    body = canonical_body(payload)
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify(secret: str, payload: Dict, signature: str) -> bool:
    expected = sign(secret, payload)
    try:
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def verify_any(secrets: Iterable[str], payload: Dict, signature: str) -> bool:
    for s in secrets:
        if verify(s, payload, signature):
            return True
    return False
