"""Document storage operations using svc-infra document management.

This module demonstrates how to use svc-infra's document storage Layer 1
for generic file management with custom metadata.
"""

from svc_infra.documents import delete_document, download_document, list_documents, upload_document
from svc_infra.storage.base import StorageBackend

from .models import DocumentCategory, DocumentResponse


async def upload_doc(
    storage: StorageBackend,
    user_id: str,
    filename: str,
    content: bytes,
    category: DocumentCategory,
    tags: list[str] | None = None,
    department: str | None = None,
    project: str | None = None,
    year: int | None = None,
) -> DocumentResponse:
    """Upload a document with metadata.

    Args:
        storage: Storage backend instance
        user_id: User uploading the document
        filename: Original filename
        content: File content as bytes
        category: Document category
        tags: Search tags (optional)
        department: Department/team (optional)
        project: Related project (optional)
        year: Document year (optional)

    Returns:
        Document response with metadata

    Example:
        >>> from svc_infra.storage import easy_storage
        >>> storage = easy_storage()
        >>> doc = await upload_doc(
        ...     storage=storage,
        ...     user_id="user_123",
        ...     filename="contract.pdf",
        ...     content=file_bytes,
        ...     category=DocumentCategory.CONTRACT,
        ...     tags=["vendor", "2024"],
        ...     department="legal"
        ... )
    """
    # Build metadata with category and custom fields
    metadata = {
        "category": category.value,
        "tags": tags or [],
        "department": department,
        "project": project,
        "year": year,
    }

    # Use svc-infra document upload (Layer 1)
    doc = await upload_document(
        storage=storage,
        user_id=user_id,
        file=content,
        filename=filename,
        metadata=metadata,
    )

    # Convert to response model
    return DocumentResponse(
        id=doc.id,
        user_id=doc.user_id,
        filename=doc.filename,
        size=doc.file_size,
        content_type=doc.content_type,
        storage_path=doc.storage_path,
        category=DocumentCategory(metadata.get("category", "other")),
        tags=metadata.get("tags", []),
        department=metadata.get("department"),
        project=metadata.get("project"),
        year=metadata.get("year"),
        uploaded_at=doc.upload_date,
    )


def list_docs(
    user_id: str,
    category: DocumentCategory | None = None,
    tags: list[str] | None = None,
    department: str | None = None,
    project: str | None = None,
    year: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DocumentResponse]:
    """List user documents with filters.

    Args:
        user_id: User identifier
        category: Filter by category (optional)
        tags: Filter by tags (any match) (optional)
        department: Filter by department (optional)
        project: Filter by project (optional)
        year: Filter by year (optional)
        limit: Maximum results (default: 100)
        offset: Pagination offset (default: 0)

    Returns:
        List of documents matching filters

    Example:
        >>> # All contracts for user
        >>> docs = list_docs(
        ...     user_id="user_123",
        ...     category=DocumentCategory.CONTRACT
        ... )
        >>>
        >>> # Legal department contracts from 2024
        >>> docs = list_docs(
        ...     user_id="user_123",
        ...     category=DocumentCategory.CONTRACT,
        ...     department="legal",
        ...     year=2024
        ... )
    """
    # Get all documents for user
    docs = list_documents(user_id=user_id, limit=limit, offset=offset)

    # Apply filters
    filtered = []
    for doc in docs:
        # Category filter
        if category and doc.metadata.get("category") != category.value:
            continue

        # Tags filter (any match)
        if tags:
            doc_tags = doc.metadata.get("tags", [])
            if not any(tag in doc_tags for tag in tags):
                continue

        # Department filter
        if department and doc.metadata.get("department") != department:
            continue

        # Project filter
        if project and doc.metadata.get("project") != project:
            continue

        # Year filter
        if year and doc.metadata.get("year") != year:
            continue

        # Convert to response model
        filtered.append(
            DocumentResponse(
                id=doc.id,
                user_id=doc.user_id,
                filename=doc.filename,
                size=doc.file_size,
                content_type=doc.content_type,
                storage_path=doc.storage_path,
                category=DocumentCategory(doc.metadata.get("category", "other")),
                tags=doc.metadata.get("tags", []),
                department=doc.metadata.get("department"),
                project=doc.metadata.get("project"),
                year=doc.metadata.get("year"),
                uploaded_at=doc.upload_date,
            )
        )

    return filtered


async def get_doc(storage: StorageBackend, document_id: str) -> DocumentResponse | None:
    """Get document by ID.

    Args:
        storage: Storage backend instance
        document_id: Document identifier

    Returns:
        Document response or None if not found

    Example:
        >>> doc = await get_doc(storage, "doc_abc123")
        >>> if doc:
        ...     print(f"Found: {doc.filename}")
    """
    from svc_infra.documents import get_document

    doc = get_document(document_id)
    if not doc:
        return None

    return DocumentResponse(
        id=doc.id,
        user_id=doc.user_id,
        filename=doc.filename,
        size=doc.file_size,
        content_type=doc.content_type,
        storage_path=doc.storage_path,
        category=DocumentCategory(doc.metadata.get("category", "other")),
        tags=doc.metadata.get("tags", []),
        department=doc.metadata.get("department"),
        project=doc.metadata.get("project"),
        year=doc.metadata.get("year"),
        uploaded_at=doc.upload_date,
    )


async def download_doc(storage: StorageBackend, document_id: str) -> bytes:
    """Download document content.

    Args:
        storage: Storage backend instance
        document_id: Document identifier

    Returns:
        File content as bytes

    Raises:
        ValueError: If document not found

    Example:
        >>> content = await download_doc(storage, "doc_abc123")
        >>> with open("downloaded.pdf", "wb") as f:
        ...     f.write(content)
    """
    return await download_document(storage=storage, document_id=document_id)


async def delete_doc(storage: StorageBackend, document_id: str) -> None:
    """Delete document.

    Args:
        storage: Storage backend instance
        document_id: Document identifier

    Raises:
        ValueError: If document not found

    Example:
        >>> await delete_doc(storage, "doc_abc123")
    """
    success = await delete_document(storage=storage, document_id=document_id)
    if not success:
        raise ValueError(f"Document not found: {document_id}")
