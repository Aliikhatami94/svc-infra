from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode())


def _sign(data: bytes, key: bytes) -> str:
    return _b64e(hmac.new(key, data, sha256).digest())


def _now() -> int:
    return int(time.time())


def sign_cookie(
    payload: Dict[str, Any],
    *,
    key: str,
    expires_in: Optional[int] = None,
) -> str:
    """Produce a compact signed cookie value with optional expiry.

    Format: base64url(json).base64url(hmac)
    If expires_in is provided, 'exp' epoch seconds is injected into payload prior to signing.
    """
    body = dict(payload)
    if expires_in is not None:
        body.setdefault("exp", _now() + int(expires_in))
    data = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    sig = _sign(data, key.encode())
    return f"{_b64e(data)}.{sig}"


def verify_cookie(
    value: str,
    *,
    key: str,
    old_keys: Optional[List[str]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Verify a signed cookie against the primary key or any old key.

    Returns (ok, payload). If ok is False, payload will be None.
    Rejects if exp is present and in the past.
    """
    if not value or "." not in value:
        return False, None
    body_b64, sig = value.split(".", 1)
    try:
        data = _b64d(body_b64)
        expected = _sign(data, key.encode())
        if not hmac.compare_digest(sig, expected):
            # try old keys
            for k in old_keys or []:
                if hmac.compare_digest(sig, _sign(data, k.encode())):
                    break
            else:
                return False, None
        payload = json.loads(data.decode())
        # Expire when current time reaches or exceeds exp
        if "exp" in payload and _now() >= int(payload["exp"]):
            return False, None
        return True, payload
    except Exception:
        return False, None


__all__ = ["sign_cookie", "verify_cookie"]
