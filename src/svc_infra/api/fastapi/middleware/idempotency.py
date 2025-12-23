import base64
import hashlib
import json
import time
from typing import Annotated

from fastapi import Header, HTTPException, Request
from starlette.types import ASGIApp, Receive, Scope, Send

from .idempotency_store import IdempotencyStore, InMemoryIdempotencyStore


class IdempotencyMiddleware:
    """
    Pure ASGI idempotency middleware.

    Caches responses for requests with Idempotency-Key header to ensure
    duplicate requests return the same response. Use skip_paths for endpoints
    where idempotency caching is not appropriate (e.g., streaming responses).

    Matching uses prefix matching: "/v1/chat" matches "/v1/chat", "/v1/chat/stream",
    but not "/api/v1/chat" or "/v1/chatter".
    """

    def __init__(
        self,
        app: ASGIApp,
        ttl_seconds: int = 24 * 3600,
        store: IdempotencyStore | None = None,
        header_name: str = "Idempotency-Key",
        skip_paths: list[str] | None = None,
    ):
        self.app = app
        self.ttl = ttl_seconds
        self.store: IdempotencyStore = store or InMemoryIdempotencyStore()
        self.header_name = header_name.lower()
        self.skip_paths = skip_paths or []

    def _cache_key(self, method: str, path: str, idkey: str) -> str:
        sig = hashlib.sha256((method + "|" + path + "|" + idkey).encode()).hexdigest()
        return f"idmp:{sig}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # Skip specified paths using prefix matching
        if any(path.startswith(skip) for skip in self.skip_paths):
            await self.app(scope, receive, send)
            return

        # Only apply to mutating methods
        if method not in {"POST", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return

        # Get idempotency key from headers
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        idkey = headers.get(self.header_name)

        if not idkey:
            # No idempotency key - pass through
            await self.app(scope, receive, send)
            return

        # Buffer the request body
        body_parts = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body_parts.append(message.get("body", b"") or b"")
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break
        body = b"".join(body_parts)

        k = self._cache_key(method, path, idkey)
        now = time.time()
        req_hash = hashlib.sha256(body).hexdigest()

        existing = self.store.get(k)
        if existing and existing.exp > now:
            # If payload mismatches, return conflict
            if existing.req_hash and existing.req_hash != req_hash:
                await self._send_json_response(
                    send,
                    409,
                    {
                        "type": "about:blank",
                        "title": "Conflict",
                        "detail": "Idempotency-Key re-used with different request payload.",
                    },
                )
                return
            # If response cached and payload matches, replay it
            if existing.status is not None and existing.body_b64 is not None:
                await self._send_cached_response(send, existing)
                return

        # Claim the key
        exp = now + self.ttl
        created = self.store.set_initial(k, req_hash, exp)
        if not created:
            existing = self.store.get(k)
            if existing and existing.req_hash and existing.req_hash != req_hash:
                await self._send_json_response(
                    send,
                    409,
                    {
                        "type": "about:blank",
                        "title": "Conflict",
                        "detail": "Idempotency-Key re-used with different request payload.",
                    },
                )
                return
            if existing and existing.status is not None and existing.body_b64 is not None:
                await self._send_cached_response(send, existing)
                return

        # Create a replay receive that returns buffered body
        # IMPORTANT: After replaying the body, we must forward to original receive()
        # so that Starlette's listen_for_disconnect can properly detect client disconnects.
        # This is required for streaming responses on ASGI spec < 2.4.
        body_sent = False

        async def replay_receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            # After body is sent, forward to original receive for disconnect detection
            return await receive()

        # Capture response for caching
        response_started = False
        response_status = 0
        response_headers: list = []
        response_body_parts = []

        async def capture_send(message):
            nonlocal response_started, response_status, response_headers
            if message["type"] == "http.response.start":
                response_started = True
                response_status = message.get("status", 200)
                response_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body_chunk = message.get("body", b"")
                if body_chunk:
                    response_body_parts.append(body_chunk)
            await send(message)

        await self.app(scope, replay_receive, capture_send)

        # Cache successful responses
        if 200 <= response_status < 300:
            response_body = b"".join(response_body_parts)
            headers_dict = {k.decode(): v.decode() for k, v in response_headers}
            media_type = headers_dict.get("content-type", "application/octet-stream")
            self.store.set_response(
                k,
                status=response_status,
                body=response_body,
                headers=headers_dict,
                media_type=media_type,
            )

    async def _send_json_response(self, send, status: int, content: dict) -> None:
        body = json.dumps(content).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})

    async def _send_cached_response(self, send, existing) -> None:
        headers = [(k.encode(), v.encode()) for k, v in (existing.headers or {}).items()]
        if existing.media_type:
            headers.append((b"content-type", existing.media_type.encode()))
        await send(
            {
                "type": "http.response.start",
                "status": existing.status,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": base64.b64decode(existing.body_b64),
                "more_body": False,
            }
        )


async def require_idempotency_key(
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    request: Request,
) -> None:
    if not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key must not be empty.")
