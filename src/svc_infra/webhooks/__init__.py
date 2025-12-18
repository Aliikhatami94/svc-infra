from __future__ import annotations

import logging
from typing import Any, cast

from .add import add_webhooks
from .encryption import decrypt_secret, encrypt_secret, is_encrypted

__all__ = [
    "add_webhooks",
    "encrypt_secret",
    "decrypt_secret",
    "is_encrypted",
    "trigger_webhook",
]

_logger = logging.getLogger(__name__)


async def trigger_webhook(
    event: str,
    data: dict[str, Any],
    *,
    webhook_service: Any | None = None,
) -> int | None:
    """
    Trigger a webhook event.

    This is a convenience function for sending webhook events. It requires
    that webhooks have been configured via add_webhooks() first.

    Args:
        event: The event/topic name (e.g., "goal.milestone_reached")
        data: The event payload data
        webhook_service: Optional WebhookService instance. If not provided,
                         attempts to use the global service from add_webhooks.

    Returns:
        The outbox message ID if successful, None if no webhook service configured.

    Example:
        from svc_infra.webhooks import trigger_webhook

        await trigger_webhook(
            event="user.created",
            data={"user_id": "123", "email": "user@example.com"}
        )

    Note:
        For this to work, you must first configure webhooks:

        from svc_infra.webhooks import add_webhooks
        add_webhooks(app)
    """
    if webhook_service is None:
        # Try to get the global webhook service from app state
        _logger.warning(
            "No webhook_service provided and no global service configured. "
            "Call add_webhooks(app) first to enable webhook delivery."
        )
        return None

    try:
        msg_id = cast("int", webhook_service.publish(event, data))
        _logger.info(f"Triggered webhook event '{event}' with message ID {msg_id}")
        return msg_id
    except Exception as e:
        _logger.error(f"Failed to trigger webhook event '{event}': {e}")
        return None
