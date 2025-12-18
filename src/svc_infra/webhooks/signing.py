from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Iterable

logger = logging.getLogger(__name__)


def canonical_body(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def sign(secret: str, payload: dict) -> str:
    body = canonical_body(payload)
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify(secret: str, payload: dict, signature: str) -> bool:
    expected = sign(secret, payload)
    try:
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.warning("Webhook signature verification failed: %s", e)
        return False


def verify_any(secrets: Iterable[str], payload: dict, signature: str) -> bool:
    for s in secrets:
        if verify(s, payload, signature):
            return True
    return False
