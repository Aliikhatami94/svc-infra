"""Encryption utilities for webhook secrets.

Provides symmetric encryption for webhook secrets stored in the outbox.
Uses Fernet (AES-128-CBC with HMAC-SHA256) for authenticated encryption.

The encryption key is derived from WEBHOOK_ENCRYPTION_KEY environment variable.
In production, this MUST be set to a securely generated 32-byte base64 key.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache
from typing import cast

from svc_infra.app.env import require_secret

# Marker prefix for encrypted values
_ENCRYPTED_PREFIX = "enc:v1:"


def _get_encryption_key() -> bytes:
    """Get the webhook encryption key, requiring it in production."""
    key_str = require_secret(
        os.getenv("WEBHOOK_ENCRYPTION_KEY"),
        "WEBHOOK_ENCRYPTION_KEY",
        dev_default="dev-only-webhook-encryption-key-not-for-production",
    )
    # If it's a Fernet key (44 chars base64), use it directly
    # Otherwise derive a key from it using SHA256
    if len(key_str) == 44 and key_str.endswith("="):
        return base64.urlsafe_b64decode(key_str)
    # Derive a 32-byte key from arbitrary string
    return hashlib.sha256(key_str.encode()).digest()


@lru_cache(maxsize=1)
def _get_fernet():
    """Get or create the Fernet cipher for encryption/decryption."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        # If cryptography is not installed, fall back to no encryption
        # but log a warning
        import logging

        logging.getLogger(__name__).warning(
            "cryptography package not installed - webhook secrets will NOT be encrypted. "
            "Install with: pip install cryptography"
        )
        return None

    key = _get_encryption_key()
    # Fernet requires a 32-byte key encoded as base64
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a webhook secret for storage.

    Args:
        plaintext: The secret to encrypt

    Returns:
        Encrypted string with "enc:v1:" prefix, or original if encryption unavailable
    """
    fernet = _get_fernet()
    if fernet is None:
        return plaintext

    encrypted = fernet.encrypt(plaintext.encode())
    return _ENCRYPTED_PREFIX + cast("str", encrypted.decode())


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a webhook secret from storage.

    Args:
        ciphertext: The encrypted secret (with "enc:v1:" prefix)

    Returns:
        Decrypted plaintext secret

    Note:
        If the value doesn't have the encryption prefix, it's returned as-is
        for backwards compatibility with existing unencrypted secrets.
    """
    # If not encrypted, return as-is (backwards compatibility)
    if not ciphertext.startswith(_ENCRYPTED_PREFIX):
        return ciphertext

    fernet = _get_fernet()
    if fernet is None:
        # Can't decrypt without cryptography - return as-is
        # This shouldn't happen in practice if encrypt_secret was used
        import logging

        logging.getLogger(__name__).error(
            "Cannot decrypt webhook secret - cryptography package not installed"
        )
        return ciphertext

    encrypted = ciphertext[len(_ENCRYPTED_PREFIX) :].encode()
    return cast("str", fernet.decrypt(encrypted).decode())


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    return value.startswith(_ENCRYPTED_PREFIX)
