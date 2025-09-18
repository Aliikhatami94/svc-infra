from __future__ import annotations

from pydantic import BaseModel, field_validator


class ServiceInfo(BaseModel):
    """Product identity (not URL)."""

    name: str = "Service Infrastructure App"
    release: str = "0.1.0"  # your app/service version, not API URL tag


class APIVersionSpec(BaseModel):
    """
    One mounted API surface. tag is the URL mount (e.g. 'v0' → /v0).
    """

    tag: str | int = "v0"
    routers_package: str | None = None
    public_base_url: str | None = None  # used to set OpenAPI `servers`
    docs: bool | None = None  # None = environment default

    @field_validator("tag", mode="before")
    @classmethod
    def _coerce_tag(cls, v):
        if isinstance(v, int):
            return f"v{v}"
        s = str(v or "").strip().lstrip("/")
        if not s:
            return "v0"
        # accept 'v0', '0', '/v1', '/1'
        if s.startswith("v"):
            return s
        if s.isdigit():
            return f"v{s}"
        return s
