"""
FastAPI integration for document management.

Mounts document endpoints with authentication and storage backend integration.
Uses svc-infra's dual router pattern for public/protected routes.

Quick Start:
    >>> from fastapi import FastAPI
    >>> from svc_infra.documents import add_documents
    >>>
    >>> app = FastAPI()
    >>> manager = add_documents(app)
    >>>
    >>> # Documents available at:
    >>> # POST /documents/upload (protected)
    >>> # GET /documents/{document_id} (protected)
    >>> # GET /documents/list (protected)
    >>> # DELETE /documents/{document_id} (protected)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from fastapi import HTTPException, Request, Response

from svc_infra.documents.models import Document

if TYPE_CHECKING:
    from fastapi import FastAPI

    from svc_infra.storage.base import StorageBackend

    from .ease import DocumentManager


def get_documents_manager(app: "FastAPI") -> "DocumentManager":
    """
    Dependency to get document manager from app state.

    Args:
        app: FastAPI application

    Returns:
        Document manager instance

    Raises:
        RuntimeError: If add_documents() has not been called
    """
    if not hasattr(app.state, "documents"):
        raise RuntimeError("Documents not configured. Call add_documents(app) first.")
    return app.state.documents


def add_documents(
    app: "FastAPI",
    storage_backend: Optional["StorageBackend"] = None,
    prefix: str = "/documents",
    tags: Optional[list[str]] = None,
) -> "DocumentManager":
    """
    Add document management endpoints to FastAPI app.

    Mounts 4 endpoints:
    1. POST /documents/upload - Upload new document
    2. GET /documents/{document_id} - Get document metadata
    3. GET /documents/list - List user's documents
    4. DELETE /documents/{document_id} - Delete document

    Args:
        app: FastAPI application
        storage_backend: Storage backend (auto-detected if None)
        prefix: URL prefix for document endpoints (default: /documents)
        tags: OpenAPI tags for documentation

    Returns:
        Document manager instance for programmatic access

    Examples:
        >>> from fastapi import FastAPI
        >>> from svc_infra.documents import add_documents
        >>>
        >>> app = FastAPI()
        >>> manager = add_documents(app)
        >>>
        >>> # Endpoints available at /documents/*
        >>> # Use manager programmatically:
        >>> doc = manager.upload("user_123", file_bytes, "file.pdf")

    Notes:
        - All routes require user authentication (uses dual router pattern)
        - Stores manager on app.state.documents for route access
        - Storage backend auto-detected from environment if not provided
    """
    from svc_infra.api.fastapi.dual.protected import user_router

    from .ease import easy_documents

    # Create manager with storage backend
    manager = easy_documents(storage_backend)

    # Store manager on app state
    app.state.documents = manager

    # Create protected router for document endpoints (requires user authentication)
    router = user_router(prefix=prefix, tags=tags or ["Documents"])

    # Route 1: Upload document
    @router.post("/upload", response_model=Document)
    async def upload_document(request: Request) -> Document:
        """
        Upload a document.

        Args:
            request: FastAPI request with form data
                - user_id (required): User uploading the document
                - file (required): File to upload
                - Any additional fields become document metadata

        Returns:
            Document metadata with storage information

        Examples:
            ```bash
            curl -X POST http://localhost:8000/documents/upload \\
              -F "user_id=user_123" \\
              -F "file=@contract.pdf" \\
              -F "category=legal" \\
              -F "year=2024"
            ```
        """
        # Parse form data
        form = await request.form()

        # Extract required fields
        user_id = form.get("user_id")
        file = form.get("file")

        if not user_id:
            raise HTTPException(status_code=422, detail="user_id is required")
        if not file or not hasattr(file, "read"):
            raise HTTPException(status_code=422, detail="file is required")

        # Read file content
        file_content = await file.read()

        # Build metadata from all other form fields
        metadata = {}
        for key, value in form.items():
            if key not in ("user_id", "file"):
                metadata[key] = value

        # Upload document
        doc = await manager.upload(
            user_id=user_id,
            file=file_content,
            filename=file.filename or "unnamed",
            metadata=metadata,
            content_type=file.content_type,
        )

        return doc

    # Route 2: List user's documents (must come before /{document_id} to avoid conflicts)
    @router.get("/list")
    async def list_user_documents(
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """
        List user's documents with pagination.

        Args:
            user_id: User identifier
            limit: Maximum number of documents (default: 100)
            offset: Number of documents to skip (default: 0)

        Returns:
            Dict with "documents", "total", "limit", "offset" keys

        Examples:
            ```bash
            # Get first page
            curl "http://localhost:8000/documents/list?user_id=user_123&limit=20"

            # Get second page
            curl "http://localhost:8000/documents/list?user_id=user_123&limit=20&offset=20"
            ```
        """
        # Get all docs for total count (before pagination)
        all_docs = manager.list(user_id=user_id, limit=999999, offset=0)
        total_count = len(all_docs)

        # Get paginated docs
        docs = manager.list(user_id=user_id, limit=limit, offset=offset)

        return {
            "documents": docs,
            "total": total_count,
            "limit": limit,
            "offset": offset,
        }

    # Route 3: Get document metadata
    @router.get("/{document_id}", response_model=Document)
    async def get_document_metadata(document_id: str) -> Document:
        """
        Get document metadata.

        Args:
            document_id: Document identifier

        Returns:
            Document metadata

        Raises:
            HTTPException: 404 if document not found

        Examples:
            ```bash
            curl http://localhost:8000/documents/doc_abc123
            ```
        """
        doc = manager.get(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    # Route 4: Delete document
    @router.delete("/{document_id}", status_code=204)
    async def delete_document_route(document_id: str) -> Response:
        """
        Delete a document and its file content.

        Args:
            document_id: Document identifier

        Returns:
            204 No Content on success

        Raises:
            HTTPException: 404 if document not found

        Examples:
            ```bash
            curl -X DELETE http://localhost:8000/documents/doc_abc123
            ```
        """
        success = await manager.delete(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return Response(status_code=204)

    # Mount router
    app.include_router(router)

    return manager
