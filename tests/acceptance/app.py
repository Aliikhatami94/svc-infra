from __future__ import annotations

from svc_infra.api.fastapi.ease import easy_service_app

# Minimal acceptance app wiring the library's routers and defaults
app = easy_service_app(
    name="svc-infra-acceptance",
    release="A0",
    versions=[
        ("v1", "svc_infra.api.fastapi.routers", None),
    ],
    root_routers=["svc_infra.api.fastapi.routers"],
    public_cors_origins=["*"],
    root_public_base_url="/",
)
