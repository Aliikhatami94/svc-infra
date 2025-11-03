from __future__ import annotations

SECURE_DEFAULTS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",
    # CSP with practical defaults - allows inline styles/scripts and data URIs for images
    # Also allows cdn.jsdelivr.net for FastAPI docs (Swagger UI, ReDoc)
    # Still secure: blocks arbitrary external scripts, prevents framing, restricts form actions
    # Override via headers_overrides in add_security() for stricter or custom policies
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
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
