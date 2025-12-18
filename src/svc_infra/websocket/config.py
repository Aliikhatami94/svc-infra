"""
WebSocket configuration with environment variable support.

Environment Variables (WS_ prefix):
    WS_OPEN_TIMEOUT: Connection timeout in seconds (default: 10.0)
    WS_CLOSE_TIMEOUT: Close handshake timeout (default: 10.0)
    WS_PING_INTERVAL: Keepalive ping interval, None to disable (default: 20.0)
    WS_PING_TIMEOUT: Pong response timeout (default: 20.0)
    WS_MAX_MESSAGE_SIZE: Max message size in bytes (default: 1048576 = 1MB)
    WS_MAX_QUEUE_SIZE: Max queued messages (default: 16)
    WS_RECONNECT_ENABLED: Enable auto-reconnection (default: true)
    WS_RECONNECT_MAX_ATTEMPTS: Max reconnect attempts, 0=infinite (default: 5)
    WS_RECONNECT_BACKOFF_BASE: Base backoff in seconds (default: 1.0)
    WS_RECONNECT_BACKOFF_MAX: Max backoff in seconds (default: 60.0)
    WS_RECONNECT_JITTER: Jitter factor 0-1 (default: 0.1)
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSocketConfig(BaseSettings):
    """WebSocket client configuration with environment variable support."""

    model_config = SettingsConfigDict(env_prefix="WS_")

    # Connection settings
    open_timeout: float = Field(default=10.0, description="Connection timeout in seconds")
    close_timeout: float = Field(default=10.0, description="Close handshake timeout in seconds")

    # Keepalive (ping/pong)
    ping_interval: float | None = Field(
        default=20.0, description="Ping interval in seconds (None to disable)"
    )
    ping_timeout: float | None = Field(default=20.0, description="Pong response timeout in seconds")

    # Message limits
    max_message_size: int = Field(
        default=1_048_576, description="Max message size in bytes (1MB default)"
    )
    max_queue_size: int = Field(default=16, description="Max queued messages")

    # Reconnection policy
    reconnect_enabled: bool = Field(default=True, description="Enable auto-reconnection")
    reconnect_max_attempts: int = Field(
        default=5, description="Max reconnect attempts (0=infinite)"
    )
    reconnect_backoff_base: float = Field(default=1.0, description="Base backoff in seconds")
    reconnect_backoff_max: float = Field(default=60.0, description="Max backoff in seconds")
    reconnect_jitter: float = Field(default=0.1, description="Jitter factor (0-1)")


def get_default_config() -> WebSocketConfig:
    """Load WebSocket config from environment with defaults."""
    return WebSocketConfig()
