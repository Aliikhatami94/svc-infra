from __future__ import annotations

SECURE_DEFAULTS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",
    # CSP kept minimal; allow config override
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}


class SecurityHeadersMiddleware:
    def __init__(self, app, overrides: dict[str, str] | None = None):
        self.app = app
        self.overrides = overrides or {}

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def _send(message):
            if message.get("type") == "http.response.start":
                headers = message.setdefault("headers", [])
                existing = {k.decode(): v.decode() for k, v in headers}
                merged = {**SECURE_DEFAULTS, **existing, **self.overrides}
                # rebuild headers list
                new_headers = []
                for k, v in merged.items():
                    new_headers.append((k.encode(), v.encode()))
                message["headers"] = new_headers
            await send(message)

        await self.app(scope, receive, _send)


__all__ = ["SecurityHeadersMiddleware", "SECURE_DEFAULTS"]
