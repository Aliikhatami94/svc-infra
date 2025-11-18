"""
In-memory storage backend for testing and development.

WARNING: Data is not persisted across restarts. Use only for testing or development.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from ..base import FileNotFoundError, InvalidKeyError, QuotaExceededError


class MemoryBackend:
    """
    In-memory storage backend.

    Stores files in memory using dictionaries. Fast and simple for testing,
    but data is lost when the process restarts.

    Args:
        max_size: Maximum total storage size in bytes (default: 100MB)
        default_expires_in: Default URL expiration in seconds (default: 3600)

    Example:
        >>> backend = MemoryBackend(max_size=10_000_000)  # 10MB max
        >>> url = await backend.put(
        ...     key="test/file.txt",
        ...     data=b"Hello, World!",
        ...     content_type="text/plain"
        ... )
    """

    def __init__(
        self,
        max_size: int = 100_000_000,  # 100MB
        default_expires_in: int = 3600,
    ):
        self.max_size = max_size
        self.default_expires_in = default_expires_in
        self._storage: dict[str, bytes] = {}
        self._metadata: dict[str, dict] = {}
        self._lock = asyncio.Lock()

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

    def _get_total_size(self) -> int:
        """Calculate total storage size."""
        return sum(len(data) for data in self._storage.values())

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store file in memory."""
        self._validate_key(key)

        async with self._lock:
            # Check quota
            current_size = self._get_total_size()
            new_size = len(data)

            # If replacing existing file, subtract its size
            if key in self._storage:
                current_size -= len(self._storage[key])

            if current_size + new_size > self.max_size:
                raise QuotaExceededError(
                    f"Storage quota exceeded. "
                    f"Current: {current_size}, New: {new_size}, Max: {self.max_size}"
                )

            # Store file
            self._storage[key] = data

            # Store metadata
            self._metadata[key] = {
                "size": len(data),
                "content_type": content_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            }

        # Return memory:// URL
        return f"memory://{key}"

    async def get(self, key: str) -> bytes:
        """Retrieve file from memory."""
        self._validate_key(key)

        async with self._lock:
            if key not in self._storage:
                raise FileNotFoundError(f"File not found: {key}")

            return self._storage[key]

    async def delete(self, key: str) -> bool:
        """Delete file from memory."""
        self._validate_key(key)

        async with self._lock:
            if key not in self._storage:
                return False

            del self._storage[key]
            del self._metadata[key]
            return True

    async def exists(self, key: str) -> bool:
        """Check if file exists in memory."""
        self._validate_key(key)

        async with self._lock:
            return key in self._storage

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
        download: bool = False,
    ) -> str:
        """
        Generate memory:// URL.

        Note: Memory backend doesn't support real URLs or expiration.
        Returns memory:// scheme for testing purposes.
        """
        self._validate_key(key)

        async with self._lock:
            if key not in self._storage:
                raise FileNotFoundError(f"File not found: {key}")

        # Memory backend doesn't support real URLs
        # Return memory:// scheme for testing
        suffix = "?download=true" if download else ""
        return f"memory://{key}{suffix}"

    async def list_keys(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> list[str]:
        """List stored keys with optional prefix filter."""
        async with self._lock:
            keys = [key for key in self._storage.keys() if key.startswith(prefix)]
            return keys[:limit]

    async def get_metadata(self, key: str) -> dict:
        """Get file metadata."""
        self._validate_key(key)

        async with self._lock:
            if key not in self._metadata:
                raise FileNotFoundError(f"File not found: {key}")

            return self._metadata[key].copy()

    async def clear(self) -> None:
        """
        Clear all stored files (testing utility).

        Example:
            >>> backend = MemoryBackend()
            >>> await backend.put("test.txt", b"data", "text/plain")
            >>> await backend.clear()
            >>> await backend.exists("test.txt")  # False
        """
        async with self._lock:
            self._storage.clear()
            self._metadata.clear()

    def get_stats(self) -> dict:
        """
        Get storage statistics (testing utility).

        Returns:
            Dict with file_count, total_size, max_size

        Example:
            >>> backend = MemoryBackend(max_size=1000)
            >>> stats = backend.get_stats()
            >>> print(f"Files: {stats['file_count']}, Size: {stats['total_size']}")
        """
        return {
            "file_count": len(self._storage),
            "total_size": self._get_total_size(),
            "max_size": self.max_size,
        }


__all__ = ["MemoryBackend"]
