"""
Base storage abstractions and exceptions.

Defines the StorageBackend protocol that all storage implementations must follow.
"""

from typing import Optional, Protocol


class StorageError(Exception):
    """Base exception for all storage operations."""

    pass


class FileNotFoundError(StorageError):
    """Raised when a requested file does not exist."""

    pass


class PermissionDeniedError(StorageError):
    """Raised when lacking permissions for an operation."""

    pass


class QuotaExceededError(StorageError):
    """Raised when storage quota is exceeded."""

    pass


class InvalidKeyError(StorageError):
    """Raised when a key format is invalid."""

    pass


class StorageBackend(Protocol):
    """
    Abstract storage backend interface.

    All storage backends must implement this protocol to be compatible
    with the storage system.

    Example:
        >>> from svc_infra.storage import StorageBackend
        >>>
        >>> class MyBackend:
        ...     async def put(self, key, data, content_type, metadata=None):
        ...         # Custom implementation
        ...         return "https://example.com/files/key"
        >>>
        >>> # MyBackend is now a valid StorageBackend
    """

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Store file content and return its URL.

        Args:
            key: Storage key (path) for the file
            data: File content as bytes
            content_type: MIME type (e.g., "image/jpeg", "application/pdf")
            metadata: Optional metadata dict (user_id, tenant_id, etc.)

        Returns:
            Public or signed URL to access the file

        Raises:
            InvalidKeyError: If key format is invalid
            PermissionDeniedError: If lacking write permissions
            QuotaExceededError: If storage quota exceeded
            StorageError: For other storage errors

        Example:
            >>> url = await storage.put(
            ...     key="avatars/user_123/profile.jpg",
            ...     data=image_bytes,
            ...     content_type="image/jpeg",
            ...     metadata={"user_id": "user_123"}
            ... )
        """
        ...

    async def get(self, key: str) -> bytes:
        """
        Retrieve file content.

        Args:
            key: Storage key (path) for the file

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file does not exist
            PermissionDeniedError: If lacking read permissions
            StorageError: For other storage errors

        Example:
            >>> data = await storage.get("avatars/user_123/profile.jpg")
        """
        ...

    async def delete(self, key: str) -> bool:
        """
        Delete a file.

        Args:
            key: Storage key (path) for the file

        Returns:
            True if file was deleted, False if file did not exist

        Raises:
            PermissionDeniedError: If lacking delete permissions
            StorageError: For other storage errors

        Example:
            >>> deleted = await storage.delete("avatars/user_123/profile.jpg")
        """
        ...

    async def exists(self, key: str) -> bool:
        """
        Check if a file exists.

        Args:
            key: Storage key (path) for the file

        Returns:
            True if file exists, False otherwise

        Example:
            >>> if await storage.exists("avatars/user_123/profile.jpg"):
            ...     print("File exists")
        """
        ...

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
        download: bool = False,
    ) -> str:
        """
        Generate a signed or public URL for file access.

        Args:
            key: Storage key (path) for the file
            expires_in: URL expiration time in seconds (default: 1 hour)
            download: If True, force download instead of inline display

        Returns:
            Signed or public URL

        Raises:
            FileNotFoundError: If file does not exist
            StorageError: For other storage errors

        Example:
            >>> # Get 1-hour signed URL for viewing
            >>> url = await storage.get_url("documents/invoice.pdf")
            >>>
            >>> # Get 5-minute download URL
            >>> url = await storage.get_url(
            ...     "documents/invoice.pdf",
            ...     expires_in=300,
            ...     download=True
            ... )
        """
        ...

    async def list_keys(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> list[str]:
        """
        List stored file keys with optional prefix filter.

        Args:
            prefix: Key prefix to filter by (e.g., "avatars/")
            limit: Maximum number of keys to return (default: 100)

        Returns:
            List of matching keys

        Example:
            >>> # List all avatars for a user
            >>> keys = await storage.list_keys(prefix="avatars/user_123/")
            >>>
            >>> # List all files
            >>> keys = await storage.list_keys()
        """
        ...

    async def get_metadata(self, key: str) -> dict:
        """
        Get file metadata.

        Args:
            key: Storage key (path) for the file

        Returns:
            Metadata dict containing:
                - size: File size in bytes
                - content_type: MIME type
                - created_at: Creation timestamp (ISO 8601)
                - Custom metadata from put() call

        Raises:
            FileNotFoundError: If file does not exist
            StorageError: For other storage errors

        Example:
            >>> meta = await storage.get_metadata("avatars/user_123/profile.jpg")
            >>> print(f"Size: {meta['size']} bytes")
            >>> print(f"Type: {meta['content_type']}")
        """
        ...


__all__ = [
    "StorageBackend",
    "StorageError",
    "FileNotFoundError",
    "PermissionDeniedError",
    "QuotaExceededError",
    "InvalidKeyError",
]
