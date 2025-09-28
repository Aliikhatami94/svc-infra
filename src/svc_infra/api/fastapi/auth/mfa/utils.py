import base64
import hashlib
import os

import pyotp


def _qr_svg_from_uri(uri: str) -> str:
    # Placeholder SVG; most frontends will render their own QR
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='280' height='280'>"
        "<rect width='100%' height='100%' fill='#fff'/>"
        f"<text x='10' y='20' font-size='10'>{uri}</text></svg>"
    )


def _random_base32() -> str:
    return pyotp.random_base32(length=32)


def _gen_recovery_codes(n: int, length: int) -> list[str]:
    out = []
    for _ in range(n):
        raw = base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")
        out.append(raw[:length])
    return out


def _gen_numeric_code(n: int = 6) -> str:
    import random

    return "".join(str(random.randrange(10)) for _ in range(n))


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _now_utc_ts() -> int:
    from datetime import datetime, timezone

    return int(datetime.now(timezone.utc).timestamp())
