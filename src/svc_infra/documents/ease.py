"""
Easy builder for document management.

Provides a simple interface for document operations with automatic
storage backend integration.

Quick Start:
    >>> from svc_infra.documents import easy_documents
    >>>
    >>> # Create manager with auto-detected storage
    >>> manager = easy_documents()
    >>>
    >>> # Upload document
    >>> doc = manager.upload(
    ...     user_id="user_123",
    ...     file=file_bytes,
    ...     filename="document.pdf",
    ...     metadata={"category": "legal"}
    ... )
    >>>
    >>> # Download document
    >>> file_data = manager.download(doc.id)
    >>>
    >>> # List user's documents
    >>> docs = manager.list(user_id="user_123")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from svc_infra.storage.base import StorageBackend

    from .models import Document


class DocumentManager:
    """
    Document manager for upload, download, and metadata operations.

    This class provides a convenient interface for all document operations,
    automatically handling storage backend integration.

    Attributes:
        storage: Storage backend instance (S3, local, memory)

    Examples:
        >>> from svc_infra.storage import easy_storage
        >>> from svc_infra.documents import DocumentManager
        >>>
        >>> storage = easy_storage()
        >>> manager = DocumentManager(storage)
        >>>
        >>> # Upload
        >>> doc = manager.upload("user_123", file_bytes, "contract.pdf")
        >>>
        >>> # Download
        >>> file_data = manager.download(doc.id)
        >>>
        >>> # List
        >>> docs = manager.list("user_123")
        >>>
        >>> # Delete
        >>> manager.delete(doc.id)
    """

    def __init__(self, storage: "StorageBackend"):
        """
        Initialize document manager.

        Args:
            storage: Storage backend instance
        """
        self.storage = storage

    async def upload(
        self,
        user_id: str,
        file: bytes,
        filename: str,
        metadata: Optional[Dict] = None,
        content_type: Optional[str] = None,
    ) -> "Document":
        """
        Upload a document.

        Args:
            user_id: User uploading the document
            file: File content as bytes
            filename: Original filename
            metadata: Optional custom metadata
            content_type: Optional MIME type

        Returns:
            Document with storage information

        Examples:
            >>> doc = await manager.upload(
            ...     user_id="user_123",
            ...     file=pdf_bytes,
            ...     filename="contract.pdf",
            ...     metadata={"category": "legal", "year": 2024}
            ... )
        """
        from .storage import upload_document

        return await upload_document(
            storage=self.storage,
            user_id=user_id,
            file=file,
            filename=filename,
            metadata=metadata,
            content_type=content_type,
        )

    async def download(self, document_id: str) -> bytes:
        """
        Download a document by ID.

        Args:
            document_id: Document identifier

        Returns:
            Document file content

        Examples:
            >>> file_data = await manager.download("doc_abc123")
            >>> with open("file.pdf", "wb") as f:
            ...     f.write(file_data)
        """
        from .storage import download_document

        return await download_document(self.storage, document_id)

    def get(self, document_id: str) -> Optional["Document"]:
        """
        Get document metadata by ID.

        Args:
            document_id: Document identifier

        Returns:
            Document metadata or None if not found

        Examples:
            >>> doc = manager.get("doc_abc123")
            >>> if doc:
            ...     print(doc.filename, doc.file_size)
        """
        from .storage import get_document

        return get_document(document_id)

    async def delete(self, document_id: str) -> bool:
        """
        Delete a document.

        Args:
            document_id: Document identifier

        Returns:
            True if deleted, False if not found

        Examples:
            >>> success = await manager.delete("doc_abc123")
        """
        from .storage import delete_document

        return await delete_document(self.storage, document_id)

    def list(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List["Document"]:
        """
        List user's documents.

        Args:
            user_id: User identifier
            limit: Maximum number of documents
            offset: Number of documents to skip

        Returns:
            List of documents

        Examples:
            >>> # Get all documents
            >>> docs = manager.list("user_123")
            >>>
            >>> # Paginated
            >>> docs = manager.list("user_123", limit=20, offset=20)
        """
        from .storage import list_documents

        return list_documents(user_id, limit, offset)


def easy_documents(storage: Optional["StorageBackend"] = None) -> DocumentManager:
    """
    Create a document manager with auto-configured storage.

    Args:
        storage: Optional storage backend (auto-detected if not provided)

    Returns:
        Document manager instance

    Examples:
        >>> # Auto-detect storage from environment
        >>> manager = easy_documents()
        >>>
        >>> # Explicit storage backend
        >>> from svc_infra.storage import easy_storage
        >>> storage = easy_storage(backend="s3")
        >>> manager = easy_documents(storage)
        >>>
        >>> # Use the manager
        >>> doc = manager.upload("user_123", file_bytes, "file.pdf")

    Notes:
        - If storage is None, uses easy_storage() to auto-detect backend
        - Auto-detection checks for Railway, S3, GCS credentials
        - Falls back to MemoryBackend if no credentials found
    """
    if storage is None:
        from svc_infra.storage import easy_storage

        storage = easy_storage()

    return DocumentManager(storage)
