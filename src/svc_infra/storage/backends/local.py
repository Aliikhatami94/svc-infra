"""
Local filesystem storage backend.

Ideal for Railway persistent volumes, Render disks, and local development.
"""

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import aiofiles
import aiofiles.os

from ..base import FileNotFoundError as StorageFileNotFoundError
from ..base import InvalidKeyError, PermissionDeniedError, StorageError


class LocalBackend:
    """
    Local filesystem storage backend.

    Stores files on the local filesystem with metadata stored as JSON sidecar files.
    Supports HMAC-based signed URLs with expiration.

    Args:
        base_path: Base directory for file storage
        base_url: Base URL for file serving (e.g., "http://localhost:8000/files")
        signing_secret: Secret key for URL signing (auto-generated if not provided)

    Example:
        >>> # Railway persistent volume
        >>> backend = LocalBackend(
        ...     base_path="/data/uploads",
        ...     base_url="https://api.example.com/files"
        ... )
        >>>
        >>> # Local development
        >>> backend = LocalBackend(
        ...     base_path="./uploads",
        ...     base_url="http://localhost:8000/files"
        ... )
    """

    def __init__(
        self,
        base_path: str = "/data/uploads",
        base_url: str = "http://localhost:8000/files",
        signing_secret: Optional[str] = None,
    ):
        self.base_path = Path(base_path)
        self.base_url = base_url.rstrip("/")
        self.signing_secret = signing_secret or secrets.token_urlsafe(32)

    def _validate_key(self, key: str) -> None:
        """Validate storage key format."""
        if not key:
            raise InvalidKeyError("Key cannot be empty")

        if key.startswith("/"):
            raise InvalidKeyError("Key cannot start with /")

        if ".." in key:
            raise InvalidKeyError("Key cannot contain .. (path traversal)")

        if len(key) > 1024:
            raise InvalidKeyError("Key cannot exceed 1024 characters")

        # Check for safe characters
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")
        if not all(c in safe_chars for c in key):
            raise InvalidKeyError(
                "Key can only contain alphanumeric, dot, dash, underscore, and slash"
            )

    def _get_file_path(self, key: str) -> Path:
        """Get absolute file path for a key."""
        return self.base_path / key

    def _get_metadata_path(self, key: str) -> Path:
        """Get metadata file path for a key."""
        return self.base_path / f"{key}.meta.json"

    def _sign_url(self, key: str, expires_at: int, download: bool) -> str:
        """Generate HMAC signature for URL."""
        message = f"{key}:{expires_at}:{download}"
        signature = hmac.new(
            self.signing_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _verify_signature(self, key: str, expires_at: int, download: bool, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = self._sign_url(key, expires_at, download)
        return hmac.compare_digest(expected, signature)

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store file on local filesystem."""
        self._validate_key(key)

        file_path = self._get_file_path(key)
        meta_path = self._get_metadata_path(key)

        try:
            # Create parent directories
            await aiofiles.os.makedirs(file_path.parent, exist_ok=True)

            # Write file atomically using temp file
            temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(data)

            # Rename to final path (atomic on POSIX)
            await aiofiles.os.rename(temp_path, file_path)

            # Write metadata
            meta_data = {
                "size": len(data),
                "content_type": content_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            }

            async with aiofiles.open(meta_path, "w") as f:
                await f.write(json.dumps(meta_data, indent=2))

        except PermissionError as e:
            raise PermissionDeniedError(f"Permission denied writing to {key}: {e}")
        except OSError as e:
            raise StorageError(f"Failed to write file {key}: {e}")

        # Return signed URL (1 hour expiration)
        return await self.get_url(key, expires_in=3600)

    async def get(self, key: str) -> bytes:
        """Retrieve file from local filesystem."""
        self._validate_key(key)

        file_path = self._get_file_path(key)

        try:
            async with aiofiles.open(file_path, "rb") as f:
                return await f.read()
        except FileNotFoundError:
            raise StorageFileNotFoundError(f"File not found: {key}")
        except PermissionError as e:
            raise PermissionDeniedError(f"Permission denied reading {key}: {e}")
        except OSError as e:
            raise StorageError(f"Failed to read file {key}: {e}")

    async def delete(self, key: str) -> bool:
        """Delete file from local filesystem."""
        self._validate_key(key)

        file_path = self._get_file_path(key)
        meta_path = self._get_metadata_path(key)

        if not file_path.exists():
            return False

        try:
            # Delete file
            await aiofiles.os.remove(file_path)

            # Delete metadata if exists
            if meta_path.exists():
                await aiofiles.os.remove(meta_path)

            return True

        except PermissionError as e:
            raise PermissionDeniedError(f"Permission denied deleting {key}: {e}")
        except OSError as e:
            raise StorageError(f"Failed to delete file {key}: {e}")

    async def exists(self, key: str) -> bool:
        """Check if file exists on local filesystem."""
        self._validate_key(key)

        file_path = self._get_file_path(key)
        return file_path.exists()

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
        download: bool = False,
    ) -> str:
        """
        Generate signed URL for file access.

        Args:
            key: Storage key
            expires_in: URL expiration in seconds (default: 1 hour)
            download: If True, force download instead of inline display

        Returns:
            Signed URL with expiration and signature

        Example:
            >>> url = await backend.get_url("avatars/user_123/profile.jpg")
            >>> # https://api.example.com/files/avatars/user_123/profile.jpg?expires=...&signature=...
        """
        self._validate_key(key)

        # Check if file exists
        if not await self.exists(key):
            raise StorageFileNotFoundError(f"File not found: {key}")

        # Calculate expiration timestamp
        expires_at = int(datetime.now(timezone.utc).timestamp()) + expires_in

        # Generate signature
        signature = self._sign_url(key, expires_at, download)

        # Build URL with query parameters
        params = {
            "expires": str(expires_at),
            "signature": signature,
        }
        if download:
            params["download"] = "true"

        url = f"{self.base_url}/{key}?{urlencode(params)}"
        return url

    def verify_url(self, key: str, expires: str, signature: str, download: bool = False) -> bool:
        """
        Verify a signed URL (for use in file serving endpoint).

        Args:
            key: Storage key
            expires: Expiration timestamp as string
            signature: HMAC signature
            download: Download flag

        Returns:
            True if signature is valid and not expired

        Example:
            >>> # In file serving route
            >>> if not backend.verify_url(key, expires, signature):
            ...     raise HTTPException(403, "Invalid signature")
        """
        try:
            expires_at = int(expires)
        except (ValueError, TypeError):
            return False

        # Check expiration
        now = int(datetime.now(timezone.utc).timestamp())
        if now > expires_at:
            return False

        # Verify signature
        return self._verify_signature(key, expires_at, download, signature)

    async def list_keys(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> list[str]:
        """List stored keys with optional prefix filter."""
        import os

        prefix_path = self.base_path / prefix if prefix else self.base_path

        if not prefix_path.exists():
            return []

        keys: list[str] = []

        # Walk directory tree (using os.walk for Python 3.11 compatibility)
        for root, _, files in os.walk(prefix_path):
            for file in files:
                # Skip metadata files
                if file.endswith(".meta.json"):
                    continue

                # Get relative path
                file_path = Path(root) / file
                relative = file_path.relative_to(self.base_path)
                key = str(relative)

                keys.append(key)

                if len(keys) >= limit:
                    return keys

        return keys

    async def get_metadata(self, key: str) -> dict:
        """Get file metadata."""
        self._validate_key(key)

        meta_path = self._get_metadata_path(key)

        if not meta_path.exists():
            # File exists but no metadata, create basic metadata
            file_path = self._get_file_path(key)
            if not file_path.exists():
                raise StorageFileNotFoundError(f"File not found: {key}")

            stat = await aiofiles.os.stat(file_path)
            return {
                "size": stat.st_size,
                "content_type": "application/octet-stream",
                "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            }

        try:
            async with aiofiles.open(meta_path, "r") as f:
                content = await f.read()
                return json.loads(content)
        except (OSError, json.JSONDecodeError) as e:
            raise StorageError(f"Failed to read metadata for {key}: {e}")


__all__ = ["LocalBackend"]
