from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator


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


class VersionInfo(BaseModel):
    # All optional; only fields you set will override the base ServiceInfo.
    title: str | None = None  # overrides info.title
    version_label: str | None = None  # overrides info.version (label only)
    description: str | None = None
    terms_of_service: str | None = None
    contact: Contact | None = None
    license: License | None = None


class APIVersionSpec(BaseModel):
    tag: str | int = "v0"
    routers_package: str | None = None
    public_base_url: str | None = None  # None -> relative "/vN"
    docs: bool | None = None
    include_api_key: bool | None = None  # per-version auth toggle

    # NEW: single, cohesive override object
    info: VersionInfo | None = None

    # ---- Back-compat shim (optional): map old per-field overrides into info ----
    # If you want to keep supporting the old fields for a while:
    description: str | None = None
    terms_of_service: str | None = None
    contact: Contact | None = None
    license: License | None = None

    @model_validator(mode="after")
    def _back_compat_into_info(self):
        if any([self.description, self.terms_of_service, self.contact, self.license]):
            vi = self.info or VersionInfo()
            if self.description is not None:
                vi.description = self.description
            if self.terms_of_service is not None:
                vi.terms_of_service = self.terms_of_service
            if self.contact is not None:
                vi.contact = self.contact
            if self.license is not None:
                vi.license = self.license
            object.__setattr__(self, "info", vi)
        return self

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
