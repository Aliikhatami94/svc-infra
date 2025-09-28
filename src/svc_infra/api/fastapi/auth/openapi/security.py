from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def install_openapi_auth(app: FastAPI) -> None:
    def _openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

        comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})

        # Only schemes Swagger UI can actually manage in the modal:
        comps.setdefault(
            "OAuth2PasswordBearer",
            {
                "type": "oauth2",
                "flows": {"password": {"tokenUrl": "/auth/login", "scopes": {}}},
            },
        )
        comps.setdefault(
            "APIKeyHeader",  # keep this exact name consistent with your routers
            {"type": "apiKey", "name": "X-API-Key", "in": "header"},
        )

        # Do NOT add a cookie scheme to avoid confusing “Authorize” options.
        # Do NOT set top-level schema["security"].

        app.openapi_schema = schema
        return schema

    app.openapi = _openapi
