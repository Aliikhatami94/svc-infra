from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class ObservabilitySettings(BaseSettings):
    """Environment-driven configuration for observability.

    Defaults are safe and vendor-neutral; downstream apps can override via env.
    """

    # Prometheus metrics
    METRICS_ENABLED: bool = Field(default=True, description="Enable Prometheus metrics exposure")
    METRICS_PATH: str = Field(default="/metrics", description="HTTP path for metrics endpoint")
    METRICS_DEFAULT_BUCKETS: tuple[float, ...] = Field(
        default=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
        description="Default histogram buckets (seconds)",
    )

    # OpenTelemetry tracing
    OTEL_ENABLED: bool = Field(default=True, description="Enable OpenTelemetry tracing")
    OTEL_SERVICE_NAME: str = Field(default="service", description="OpenTelemetry service.name")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4317", description="OTLP endpoint for Collector"
    )
    OTEL_EXPORTER_PROTOCOL: str = Field(
        default="grpc", description='Exporter protocol: "grpc" or "http/protobuf"'
    )
    OTEL_SAMPLER_RATIO: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Trace sampling ratio"
    )

    model_config = {
        "env_prefix": "",
        "extra": "ignore",
    }
