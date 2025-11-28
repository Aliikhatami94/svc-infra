"""
Data models for WebSocket infrastructure.

Provides:
- ConnectionState: Enum for connection lifecycle states
- WebSocketMessage: Wrapper for messages with metadata
- ConnectionInfo: Metadata for tracked connections
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConnectionState(str, Enum):
    """WebSocket connection lifecycle states."""

    CONNECTING = "connecting"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


class WebSocketMessage(BaseModel):
    """Wrapper for WebSocket messages with metadata."""

    data: str | bytes = Field(..., description="Message content (text or binary)")
    is_binary: bool = Field(default=False, description="True if data is binary")
    received_at: datetime | None = Field(
        default=None, description="Timestamp when message was received"
    )

    model_config = {"arbitrary_types_allowed": True}


class ConnectionInfo(BaseModel):
    """Metadata for a tracked WebSocket connection."""

    user_id: str = Field(..., description="User identifier")
    connection_id: str = Field(..., description="Unique connection identifier")
    connected_at: datetime = Field(..., description="When connection was established")
    last_activity: datetime = Field(..., description="Last message activity timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional connection metadata"
    )
