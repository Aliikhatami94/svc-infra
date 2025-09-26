from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .settings import get_auth_settings


def install_openapi_auth(app: FastAPI) -> None:
    def _openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

        st = get_auth_settings()
        comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        comps.update(
            {
                "OAuth2PasswordBearer": {
                    "type": "oauth2",
                    "flows": {"password": {"tokenUrl": "/auth/login", "scopes": {}}},
                },
                # JWT-in-cookie (your session token)
                "SessionCookie": {"type": "apiKey", "name": st.auth_cookie_name, "in": "cookie"},
                # API keys for service-to-service calls
                "ApiKeyHeader": {"type": "apiKey", "name": "X-API-Key", "in": "header"},
            }
        )

        # Make credentials optional but available for all operations by default.
        schema["security"] = [
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
            {"ApiKeyHeader": []},
        ]

        app.openapi_schema = schema
        return schema

    app.openapi = _openapi
