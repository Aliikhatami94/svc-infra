from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class UptraceEnv:
    """App-side env needed to talk to Uptrace."""

    mode: str  # "uptrace" (or "both")
    service_name: str  # OTEL_SERVICE_NAME
    otlp_endpoint: str  # e.g., "http://uptrace:4317"
    protocol: str  # "grpc" or "http/protobuf"
    dsn: Optional[str]  # UPTRACE_DSN (optional but recommended)

    def as_export(self) -> dict[str, str]:
        env = {
            "OBS_MODE": self.mode,
            "OTEL_SERVICE_NAME": self.service_name,
            "OTEL_EXPORTER_OTLP_ENDPOINT": self.otlp_endpoint,
            "OTEL_EXPORTER_PROTOCOL": self.protocol,
        }
        if self.dsn:
            env["UPTRACE_DSN"] = self.dsn
        return env


def default_service_name() -> str:
    try:
        return Path.cwd().name.replace("_", "-")
    except Exception:
        return "service"


def make_uptrace_env(
    *,
    service_name: Optional[str] = None,
    dsn: Optional[str] = None,
    endpoint: Optional[str] = None,
    protocol: str = "grpc",
    mode: str = "uptrace",
) -> UptraceEnv:
    return UptraceEnv(
        mode=mode,
        service_name=service_name or os.getenv("OTEL_SERVICE_NAME") or default_service_name(),
        otlp_endpoint=endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://uptrace:4317",
        protocol=protocol or os.getenv("OTEL_EXPORTER_PROTOCOL") or "grpc",
        dsn=dsn or os.getenv("UPTRACE_DSN"),
    )
