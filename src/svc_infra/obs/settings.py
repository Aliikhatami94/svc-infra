from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class ObservabilitySettings(BaseSettings):
    """
    Observability config (Grafana/Prometheus only).

    Env vars:
      - METRICS_ENABLED=true|false
      - METRICS_PATH=/metrics
      - METRICS_DEFAULT_BUCKETS=comma-separated seconds (optional)
    """

    METRICS_ENABLED: bool = Field(default=True, description="Enable Prometheus metrics exposure")
    METRICS_PATH: str = Field(default="/metrics", description="HTTP path for metrics endpoint")
    METRICS_DEFAULT_BUCKETS: tuple[float, ...] = Field(
        default=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
        description="Default histogram buckets (seconds)",
    )

    model_config = {
        "env_prefix": "",
        "extra": "ignore",
    }
