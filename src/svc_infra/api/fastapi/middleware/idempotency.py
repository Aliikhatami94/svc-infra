import base64
import hashlib
import time
from typing import Annotated, Dict, Optional

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from .idempotency_store import IdempotencyStore, InMemoryIdempotencyStore


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        ttl_seconds: int = 24 * 3600,
        store: Optional[IdempotencyStore] = None,
        header_name: str = "Idempotency-Key",
    ):
        super().__init__(app)
        self.ttl = ttl_seconds
        self.store: IdempotencyStore = store or InMemoryIdempotencyStore()
        self.header_name = header_name

    def _cache_key(self, request, idkey: str):
        # The cache key must NOT include the body to allow conflict detection for mismatched payloads.
        sig = hashlib.sha256(
            (request.method + "|" + request.url.path + "|" + idkey).encode()
        ).hexdigest()
        return f"idmp:{sig}"

    async def dispatch(self, request, call_next):
        if request.method in {"POST", "PATCH", "DELETE"}:
            # read & buffer body once
            body = await request.body()
            request._body = body
            idkey = request.headers.get(self.header_name)
            if idkey:
                k = self._cache_key(request, idkey)
                now = time.time()
                # build request hash to detect mismatched replays
                req_hash = hashlib.sha256(body or b"").hexdigest()

                existing = self.store.get(k)
                if existing and existing.exp > now:
                    # If payload mismatches any existing claim, return conflict
                    if existing.req_hash and existing.req_hash != req_hash:
                        return JSONResponse(
                            status_code=409,
                            content={
                                "type": "about:blank",
                                "title": "Conflict",
                                "detail": "Idempotency-Key re-used with different request payload.",
                            },
                        )
                    # If response cached and payload matches, replay it
                    if existing.status is not None and existing.body_b64 is not None:
                        return Response(
                            content=base64.b64decode(existing.body_b64),
                            status_code=existing.status,
                            headers=existing.headers or {},
                            media_type=existing.media_type,
                        )

                # Claim the key if not present
                exp = now + self.ttl
                created = self.store.set_initial(k, req_hash, exp)
                if not created:
                    # Someone else claimed; re-check for conflict or replay
                    existing = self.store.get(k)
                    if existing and existing.req_hash and existing.req_hash != req_hash:
                        return JSONResponse(
                            status_code=409,
                            content={
                                "type": "about:blank",
                                "title": "Conflict",
                                "detail": "Idempotency-Key re-used with different request payload.",
                            },
                        )
                    if existing and existing.status is not None and existing.body_b64 is not None:
                        return Response(
                            content=base64.b64decode(existing.body_b64),
                            status_code=existing.status,
                            headers=existing.headers or {},
                            media_type=existing.media_type,
                        )

                # Proceed to handler
                resp = await call_next(request)
                if 200 <= resp.status_code < 300:
                    body_bytes = b"".join([section async for section in resp.body_iterator])
                    headers: Dict[str, str] = dict(resp.headers)
                    self.store.set_response(
                        k,
                        status=resp.status_code,
                        body=body_bytes,
                        headers=headers,
                        media_type=resp.media_type,
                    )
                    return Response(
                        content=body_bytes,
                        status_code=resp.status_code,
                        headers=headers,
                        media_type=resp.media_type,
                    )
                return resp
        return await call_next(request)


async def require_idempotency_key(
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    request: Request,
) -> None:
    if not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key must not be empty.")
