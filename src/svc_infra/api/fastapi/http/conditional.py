from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from hashlib import sha256

from fastapi import Request, Response


def compute_etag(payload: bytes) -> str:
    return '"' + sha256(payload).hexdigest() + '"'


def set_conditional_headers(
    resp: Response, etag: str | None = None, last_modified: datetime | None = None
):
    if etag:
        resp.headers["ETag"] = etag
    if last_modified:
        if last_modified.tzinfo is None:
            last_modified = last_modified.replace(tzinfo=timezone.utc)
        resp.headers["Last-Modified"] = format_datetime(last_modified)


def maybe_not_modified(request: Request, etag: str | None, last_modified: datetime | None) -> bool:
    inm = request.headers.get("If-None-Match")
    ims = request.headers.get("If-Modified-Since")
    etag_ok = etag and inm and etag in [t.strip() for t in inm.split(",")]
    time_ok = False
    if last_modified and ims:
        try:
            time_ok = parsedate_to_datetime(ims) >= last_modified
        except Exception:
            pass
    return bool(etag_ok or time_ok)
