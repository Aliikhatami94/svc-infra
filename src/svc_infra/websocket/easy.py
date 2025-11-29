"""
Easy builders for WebSocket infrastructure.

Provides simple factory functions with sensible defaults.

Example:
    from svc_infra.websocket import websocket_client

    async with websocket_client("wss://api.openai.com/v1/realtime") as ws:
        await ws.send_json({"type": "session.update"})
        async for event in ws:
            print(event)
"""

from __future__ import annotations

from typing import Any

from .client import WebSocketClient
from .config import WebSocketConfig, get_default_config


def websocket_client(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    subprotocols: list[str] | None = None,
    **config_overrides: Any,
) -> WebSocketClient:
    """
    Create a WebSocket client with sensible defaults.

    Config can be overridden via kwargs or WS_* environment variables.

    Args:
        url: WebSocket URL to connect to
        headers: Optional headers to send with the connection
        subprotocols: Optional list of subprotocols to negotiate
        **config_overrides: Override any WebSocketConfig field

    Returns:
        WebSocketClient ready to be used as async context manager

    Example:
        async with websocket_client("wss://api.openai.com/v1/realtime") as ws:
            await ws.send_json({"type": "session.update"})
            async for event in ws:
                print(event)

        # With custom config
        async with websocket_client(
            "wss://...",
            headers={"Authorization": "Bearer token"},
            ping_interval=30,
            max_message_size=16 * 1024 * 1024,  # 16MB for audio
        ) as ws:
            ...
    """
    config = get_default_config()

    # Apply any overrides
    if config_overrides:
        config_dict = config.model_dump()
        config_dict.update(config_overrides)
        config = WebSocketConfig(**config_dict)

    return WebSocketClient(
        url,
        config=config,
        headers=headers,
        subprotocols=subprotocols,
    )


# Backward compatibility alias
easy_websocket_client = websocket_client
