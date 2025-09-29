from __future__ import annotations

from pydantic import BaseModel, field_validator


class Contact(BaseModel):
    name: str | None = None
    email: str | None = None
    url: str | None = None


class License(BaseModel):
    name: str | None = None
    url: str | None = None


class ServiceInfo(BaseModel):
    name: str = "Service Infrastructure App"
    release: str = "0.1.0"
    description: str | None = None
    terms_of_service: str | None = None
    contact: Contact | None = None
    license: License | None = None


class APIVersionSpec(BaseModel):
    tag: str | int = "v0"
    routers_package: str | None = None
    public_base_url: str | None = None  # None -> relative "/vN"
    docs: bool | None = None

    # NEW: per-child OpenAPI overrides
    description: str | None = None
    terms_of_service: str | None = None
    contact: Contact | None = None
    license: License | None = None
    include_api_key: bool | None = None  # None -> inherit default you choose

    @field_validator("tag", mode="before")
    @classmethod
    def _coerce_tag(cls, v):
        if isinstance(v, int):
            return f"v{v}"
        s = str(v or "").strip().lstrip("/")
        if not s:
            return "v0"
        if s.startswith("v"):
            return s
        if s.isdigit():
            return f"v{s}"
        return s
