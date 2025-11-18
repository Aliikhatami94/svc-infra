"""FastAPI router for document management endpoints.

This demonstrates how to create REST endpoints using svc-infra's
document storage with custom business logic and metadata.
"""

from typing import Optional

from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from svc_infra.api.fastapi.dual.public import public_router
from svc_infra.storage import easy_storage
from svc_infra.storage.base import StorageBackend

from .models import DocumentCategory, DocumentResponse, DocumentUploadRequest
from .storage import delete_doc, download_doc, get_doc, list_docs, upload_doc

# Create router using svc-infra's public_router (no auth required for demo)
router = public_router(prefix="/documents", tags=["Documents"])


# Dependency to get storage backend
def get_storage() -> StorageBackend:
    """Get storage backend instance."""
    return easy_storage()


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document_endpoint(
    request: DocumentUploadRequest,
    storage: StorageBackend = Depends(get_storage),
) -> DocumentResponse:
    """Upload a document with metadata.

    This endpoint demonstrates generic document upload with:
    - Custom metadata (category, tags, department, etc.)
    - Storage backend integration
    - Response with document details

    Example:
        ```bash
        curl -X POST http://localhost:8000/documents/upload \\
          -H "Content-Type: application/json" \\
          -d '{
            "user_id": "user_123",
            "filename": "contract.pdf",
            "content": "base64_encoded_content_here",
            "category": "contract",
            "tags": ["vendor", "2024"],
            "department": "legal"
          }'
        ```
    """
    # Convert content to bytes (assuming base64 or text)
    content_bytes = (
        request.content.encode() if isinstance(request.content, str) else request.content
    )

    return await upload_doc(
        storage=storage,
        user_id=request.user_id,
        filename=request.filename,
        content=content_bytes,
        category=request.category,
        tags=request.tags,
        department=request.department,
        project=request.project,
        year=request.year,
    )


@router.post("/upload-file", response_model=DocumentResponse, status_code=201)
async def upload_file_endpoint(
    user_id: str = Form(...),
    category: DocumentCategory = Form(...),
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),  # Comma-separated
    department: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    storage: StorageBackend = Depends(get_storage),
) -> DocumentResponse:
    """Upload a document file with multipart form data.

    This endpoint accepts actual file uploads (multipart/form-data).

    Example:
        ```bash
        curl -X POST http://localhost:8000/documents/upload-file \\
          -F "user_id=user_123" \\
          -F "category=contract" \\
          -F "tags=vendor,2024" \\
          -F "department=legal" \\
          -F "file=@contract.pdf"
        ```
    """
    # Read file content
    content = await file.read()

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    return await upload_doc(
        storage=storage,
        user_id=user_id,
        filename=file.filename or "unnamed",
        content=content,
        category=category,
        tags=tag_list,
        department=department,
        project=project,
        year=year,
    )


@router.get("/list", response_model=list[DocumentResponse])
async def list_documents_endpoint(
    user_id: str,
    category: Optional[DocumentCategory] = None,
    tags: Optional[str] = None,  # Comma-separated
    department: Optional[str] = None,
    project: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DocumentResponse]:
    """List user documents with filters.

    Example:
        ```bash
        # All documents
        curl http://localhost:8000/documents/list?user_id=user_123

        # Contracts only
        curl http://localhost:8000/documents/list?user_id=user_123&category=contract

        # Legal department contracts from 2024
        curl http://localhost:8000/documents/list?user_id=user_123&category=contract&department=legal&year=2024

        # Documents with specific tags
        curl http://localhost:8000/documents/list?user_id=user_123&tags=vendor,important
        ```
    """
    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    return list_docs(
        user_id=user_id,
        category=category,
        tags=tag_list,
        department=department,
        project=project,
        year=year,
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_endpoint(
    document_id: str,
    storage: StorageBackend = Depends(get_storage),
) -> DocumentResponse:
    """Get document metadata by ID.

    Example:
        ```bash
        curl http://localhost:8000/documents/doc_abc123
        ```
    """
    doc = await get_doc(storage, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


@router.get("/{document_id}/download")
async def download_document_endpoint(
    document_id: str,
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    """Download document content.

    Example:
        ```bash
        curl http://localhost:8000/documents/doc_abc123/download -o downloaded.pdf
        ```
    """
    try:
        # Get document metadata first
        doc = await get_doc(storage, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

        # Download content
        content = await download_doc(storage, document_id)

        # Return as file download
        return Response(
            content=content,
            media_type=doc.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{doc.filename}"',
                "Content-Length": str(len(content)),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{document_id}", status_code=204)
async def delete_document_endpoint(
    document_id: str,
    storage: StorageBackend = Depends(get_storage),
) -> None:
    """Delete a document.

    Example:
        ```bash
        curl -X DELETE http://localhost:8000/documents/doc_abc123
        ```
    """
    try:
        await delete_doc(storage, document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
