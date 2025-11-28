"""
WebSocket exception types.

Provides a hierarchy of exceptions for WebSocket operations:
- WebSocketError: Base exception for all WebSocket errors
- ConnectionClosedError: Connection was closed unexpectedly
- ConnectionFailedError: Failed to establish connection
- AuthenticationError: WebSocket authentication failed
- MessageTooLargeError: Message exceeds max_message_size
"""

from __future__ import annotations


class WebSocketError(Exception):
    """Base exception for WebSocket operations."""

    pass


class ConnectionClosedError(WebSocketError):
    """Connection was closed unexpectedly.

    Attributes:
        code: WebSocket close code (e.g., 1000 for normal, 1006 for abnormal)
        reason: Close reason message
    """

    def __init__(self, code: int | None = None, reason: str = ""):
        self.code = code
        self.reason = reason
        super().__init__(f"Connection closed: {code} {reason}".strip())


class ConnectionFailedError(WebSocketError):
    """Failed to establish WebSocket connection.

    Raised when the initial connection handshake fails due to network
    issues, invalid URL, server rejection, etc.
    """

    pass


class AuthenticationError(WebSocketError):
    """WebSocket authentication failed.

    Raised when JWT validation fails or required credentials are missing.
    """

    pass


class MessageTooLargeError(WebSocketError):
    """Message exceeds max_message_size configuration.

    Raised when attempting to send or receive a message larger than
    the configured maximum.
    """

    pass
