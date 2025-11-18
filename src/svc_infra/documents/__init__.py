"""
Generic document management for svc-infra.

This module provides domain-agnostic document storage and metadata management
that works with any storage backend (S3, local, memory). For domain-specific
extensions (e.g., OCR for tax forms, medical record parsing), see fin-infra
as a reference implementation.

Quick Start:
    >>> from svc_infra.documents import easy_documents
    >>>
    >>> # Create manager (auto-detects storage backend)
    >>> manager = easy_documents()
    >>>
    >>> # Upload document
    >>> doc = manager.upload(
    ...     user_id="user_123",
    ...     file=file_bytes,
    ...     filename="contract.pdf",
    ...     metadata={"category": "legal", "year": 2024}
    ... )
    >>>
    >>> # List documents
    >>> docs = manager.list(user_id="user_123")
    >>>
    >>> # Download document
    >>> file_data = manager.download(doc.id)
    >>>
    >>> # Delete document
    >>> manager.delete(doc.id)

FastAPI Integration:
    >>> from fastapi import FastAPI
    >>> from svc_infra.documents import add_documents
    >>>
    >>> app = FastAPI()
    >>> manager = add_documents(app)
    >>>
    >>> # Routes available:
    >>> # POST /documents/upload
    >>> # GET /documents/{id}
    >>> # GET /documents/list
    >>> # DELETE /documents/{id}

Architecture:
    - Generic document model with flexible metadata
    - Storage backend integration (uses svc-infra.storage)
    - SQL metadata storage (currently in-memory, SQL coming soon)
    - FastAPI router with 4 endpoints
    - No domain-specific logic (extensible for any use case)

Extension Pattern:
    For domain-specific features, import from this module and extend:

    >>> # fin-infra example (financial documents with OCR/AI)
    >>> from svc_infra.documents import Document, DocumentManager
    >>>
    >>> class FinancialDocument(Document):
    ...     '''Extends base with financial fields'''
    ...     tax_year: int
    ...     form_type: str
    >>>
    >>> class FinancialDocumentManager(DocumentManager):
    ...     '''Extends base with OCR and AI analysis'''
    ...     def extract_text(self, doc_id: str):
    ...         '''OCR for tax forms'''
    ...         pass
    ...     def analyze(self, doc_id: str):
    ...         '''AI-powered insights'''
    ...         pass
"""

from .add import add_documents
from .ease import DocumentManager, easy_documents
from .models import Document
from .storage import (
    clear_storage,
    delete_document,
    download_document,
    get_document,
    list_documents,
    upload_document,
)

__all__ = [
    # Models
    "Document",
    # Manager
    "DocumentManager",
    "easy_documents",
    # Storage operations
    "upload_document",
    "get_document",
    "download_document",
    "delete_document",
    "list_documents",
    "clear_storage",
    # FastAPI integration
    "add_documents",
]
