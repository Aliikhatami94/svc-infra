import hashlib
import time

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, ttl_seconds: int = 24 * 3600, store=None):
        super().__init__(app)
        self.ttl = ttl_seconds
        self.store = store or {}  # replace with Redis

    def _cache_key(self, request, idkey: str):
        body = getattr(request, "_body", None)
        if body is None:
            body = b""

            async def _read():
                data = await request.body()
                request._body = data  # stash for downstream
                return data

            # read once
            # note: starlette Request is awaitable; we read in dispatch below

        sig = hashlib.sha256(
            (
                request.method + "|" + request.url.path + "|" + idkey + "|" + (request._body or b"")
            ).encode()
            if isinstance(request._body, str)
            else (request.method + "|" + request.url.path + "|" + idkey).encode()
            + (request._body or b"")
        ).hexdigest()
        return f"idmp:{sig}"

    async def dispatch(self, request, call_next):
        if request.method in {"POST", "PATCH", "DELETE"}:
            # read & buffer body once
            body = await request.body()
            request._body = body
            idkey = request.headers.get("Idempotency-Key")
            if idkey:
                k = self._cache_key(request, idkey)
                entry = self.store.get(k)
                now = time.time()
                if entry and entry["exp"] > now:
                    cached = entry["resp"]
                    return Response(
                        content=cached["body"],
                        status_code=cached["status"],
                        headers=cached["headers"],
                        media_type=cached.get("media_type"),
                    )
                resp = await call_next(request)
                # cache only 2xx/201 responses
                if 200 <= resp.status_code < 300:
                    body_bytes = b"".join([section async for section in resp.body_iterator])
                    headers = dict(resp.headers)
                    self.store[k] = {
                        "resp": {
                            "status": resp.status_code,
                            "body": body_bytes,
                            "headers": headers,
                            "media_type": resp.media_type,
                        },
                        "exp": now + self.ttl,
                    }
                    return Response(
                        content=body_bytes,
                        status_code=resp.status_code,
                        headers=headers,
                        media_type=resp.media_type,
                    )
                return resp
        return await call_next(request)


async def require_idempotency_key(
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    request: Request = None,
) -> None:
    if not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key must not be empty.")
