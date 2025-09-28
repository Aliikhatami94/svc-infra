from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from svc_infra.api.fastapi.auth.settings import get_auth_settings


def install_openapi_auth(app: FastAPI) -> None:
    def _openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        st = get_auth_settings()

        comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})

        # Merge without clobbering existing definitions.
        comps.setdefault(
            "OAuth2PasswordBearer",
            {
                "type": "oauth2",
                "flows": {"password": {"tokenUrl": "/auth/login", "scopes": {}}},
            },
        )
        comps.setdefault(
            "SessionCookie",
            {"type": "apiKey", "name": st.auth_cookie_name, "in": "cookie"},
        )
        comps.setdefault(  # NOTE: capitalized key
            "APIKeyHeader",
            {"type": "apiKey", "name": "X-API-Key", "in": "header"},
        )

        # Do NOT set top-level schema["security"] here.

        app.openapi_schema = schema
        return schema

    app.openapi = _openapi
