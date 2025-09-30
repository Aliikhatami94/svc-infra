from __future__ import annotations

from typing import Callable

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

SchemaMutator = Callable[[dict], dict]


def apply_mutators(app: FastAPI, *mutators):
    previous = getattr(app, "openapi", None)

    def patched():
        base_schema = (
            previous()
            if callable(previous)
            else get_openapi(title=app.title, version=app.version, routes=app.routes)
        )
        schema = dict(base_schema)
        for m in mutators:
            schema = m(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = patched
