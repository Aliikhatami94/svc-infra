"""
Document storage operations using svc-infra storage backend.

This module provides CRUD operations for document management, storing file content
in the configured storage backend (S3, local, memory) and metadata in SQL.

Quick Start:
    >>> import asyncio
    >>> from svc_infra.storage import easy_storage
    >>> from svc_infra.documents.storage import upload_document, get_document
    >>>
    >>> storage = easy_storage()
    >>> doc = await upload_document(
    ...     storage=storage,
    ...     user_id="user_123",
    ...     file=b"file content",
    ...     filename="document.pdf",
    ...     metadata={"category": "legal"}
    ... )
    >>> print(doc.id, doc.storage_path)
"""

from __future__ import annotations

import hashlib
import mimetypes
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from svc_infra.storage.base import StorageBackend

    from .models import Document

# In-memory metadata storage (production: use SQL database)
# This is a temporary solution until SQL integration is complete
_documents_metadata: Dict[str, "Document"] = {}


async def upload_document(
    storage: "StorageBackend",
    user_id: str,
    file: bytes,
    filename: str,
    metadata: Optional[Dict] = None,
    content_type: Optional[str] = None,
) -> "Document":
    """
    Upload a document with file content to storage backend.

    Args:
        storage: Storage backend instance (S3, local, memory)
        user_id: User uploading the document
        file: File content as bytes
        filename: Original filename
        metadata: Optional custom metadata dictionary
        content_type: Optional MIME type (auto-detected if not provided)

    Returns:
        Document with storage information and metadata

    Examples:
        >>> from svc_infra.storage import easy_storage
        >>> storage = easy_storage()
        >>>
        >>> # Upload PDF document
        >>> doc = upload_document(
        ...     storage=storage,
        ...     user_id="user_123",
        ...     file=pdf_bytes,
        ...     filename="contract.pdf",
        ...     metadata={"category": "legal", "year": 2024}
        ... )
        >>>
        >>> # Upload image
        >>> doc = upload_document(
        ...     storage=storage,
        ...     user_id="user_456",
        ...     file=image_bytes,
        ...     filename="photo.jpg",
        ...     content_type="image/jpeg"
        ... )

    Notes:
        - Current: In-memory metadata storage (for development)
        - Production: Store metadata in SQL database using svc-infra SQL helpers
        - Storage path format: documents/{user_id}/{doc_id}/{filename}
        - Checksum: SHA-256 hash for integrity validation
    """
    from .models import Document

    # Generate unique document ID
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"

    # Build storage path with user isolation
    storage_path = f"documents/{user_id}/{doc_id}/{filename}"

    # Detect content type if not provided
    if content_type is None:
        detected_type, _ = mimetypes.guess_type(filename)
        content_type = detected_type or "application/octet-stream"

    # Calculate checksum for integrity
    checksum = f"sha256:{hashlib.sha256(file).hexdigest()}"

    # Upload file to storage backend
    await storage.put(storage_path, file, content_type=content_type, metadata=metadata or {})

    # Create document metadata
    doc = Document(
        id=doc_id,
        user_id=user_id,
        filename=filename,
        file_size=len(file),
        upload_date=datetime.utcnow(),
        storage_path=storage_path,
        content_type=content_type,
        checksum=checksum,
        metadata=metadata or {},
    )

    # Store metadata (production: use SQL)
    _documents_metadata[doc_id] = doc

    return doc


def get_document(document_id: str) -> Optional["Document"]:
    """
    Get document metadata by ID.

    Args:
        document_id: Document identifier

    Returns:
        Document metadata or None if not found

    Examples:
        >>> doc = get_document("doc_abc123")
        >>> if doc:
        ...     print(doc.filename, doc.file_size)
    """
    return _documents_metadata.get(document_id)


async def download_document(storage: "StorageBackend", document_id: str) -> bytes:
    """
    Download document file content from storage.

    Args:
        storage: Storage backend instance
        document_id: Document identifier

    Returns:
        Document file content as bytes

    Raises:
        ValueError: If document not found

    Examples:
        >>> from svc_infra.storage import easy_storage
        >>> storage = easy_storage()
        >>>
        >>> file_data = await download_document(storage, "doc_abc123")
        >>> with open("downloaded.pdf", "wb") as f:
        ...     f.write(file_data)
    """
    doc = get_document(document_id)
    if not doc:
        raise ValueError(f"Document not found: {document_id}")

    # Download from storage backend
    return await storage.get(doc.storage_path)


async def delete_document(storage: "StorageBackend", document_id: str) -> bool:
    """
    Delete document and its file content.

    Args:
        storage: Storage backend instance
        document_id: Document identifier

    Returns:
        True if deleted, False if not found

    Examples:
        >>> from svc_infra.storage import easy_storage
        >>> storage = easy_storage()
        >>>
        >>> success = delete_document(storage, "doc_abc123")
        >>> if success:
        ...     print("Document deleted")
    """
    doc = get_document(document_id)
    if not doc:
        return False

    # Delete from storage backend
    await storage.delete(doc.storage_path)

    # Delete metadata (production: use SQL)
    del _documents_metadata[document_id]

    return True


def list_documents(
    user_id: str,
    limit: int = 100,
    offset: int = 0,
) -> List["Document"]:
    """
    List user's documents with pagination.

    Args:
        user_id: User identifier
        limit: Maximum number of documents to return
        offset: Number of documents to skip

    Returns:
        List of user's documents

    Examples:
        >>> # Get first page
        >>> docs = list_documents("user_123", limit=20)
        >>>
        >>> # Get second page
        >>> docs = list_documents("user_123", limit=20, offset=20)
        >>>
        >>> # Filter by metadata (future enhancement)
        >>> # docs = list_documents("user_123", filters={"category": "legal"})

    Notes:
        - Current: In-memory filtering
        - Production: Use SQL queries with proper indexing
        - Future: Add metadata filtering and sorting
    """
    # Filter by user (production: SQL query)
    user_docs = [doc for doc in _documents_metadata.values() if doc.user_id == user_id]

    # Sort by upload date (newest first)
    user_docs.sort(key=lambda d: d.upload_date, reverse=True)

    # Apply pagination
    return user_docs[offset : offset + limit]


def clear_storage() -> None:
    """
    Clear all document metadata (for testing only).

    Warning:
        This does NOT delete files from storage backend.
        Only use in test environments.

    Examples:
        >>> # In tests
        >>> clear_storage()
    """
    _documents_metadata.clear()
