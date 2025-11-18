"""
Generic document models for file management.

This module provides domain-agnostic document metadata models that work with
any type of file (PDFs, images, videos, etc.). For domain-specific extensions
(e.g., tax forms, medical records), see implementation examples in fin-infra.

Quick Start:
    >>> from svc_infra.documents import Document
    >>>
    >>> doc = Document(
    ...     id="doc_abc123",
    ...     user_id="user_123",
    ...     filename="contract.pdf",
    ...     file_size=524288,
    ...     storage_path="documents/user_123/doc_abc123.pdf",
    ...     content_type="application/pdf",
    ...     metadata={"category": "legal", "year": 2024}
    ... )
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    """
    Generic document metadata and storage information.

    This is a base model for any type of document. Domain-specific applications
    should extend this model with additional fields as needed.

    Attributes:
        id: Unique document identifier (e.g., "doc_abc123")
        user_id: User who owns/uploaded the document
        filename: Original filename
        file_size: File size in bytes
        upload_date: When document was uploaded (UTC)
        storage_path: Storage backend path/key
        content_type: MIME type (e.g., "application/pdf", "image/jpeg")
        checksum: Optional file checksum for integrity validation
        metadata: Flexible metadata dictionary for custom fields

    Examples:
        >>> # Legal document
        >>> doc = Document(
        ...     id="doc_abc123",
        ...     user_id="user_123",
        ...     filename="employment_contract.pdf",
        ...     file_size=524288,
        ...     storage_path="documents/user_123/2024/legal/doc_abc123.pdf",
        ...     content_type="application/pdf",
        ...     metadata={"category": "legal", "type": "contract", "year": 2024}
        ... )
        >>>
        >>> # Medical record
        >>> doc = Document(
        ...     id="doc_def456",
        ...     user_id="patient_789",
        ...     filename="lab_results.pdf",
        ...     file_size=102400,
        ...     storage_path="documents/patient_789/2024/medical/doc_def456.pdf",
        ...     content_type="application/pdf",
        ...     metadata={"category": "medical", "test_type": "blood_work", "date": "2024-11-18"}
        ... )
        >>>
        >>> # Invoice
        >>> doc = Document(
        ...     id="doc_ghi789",
        ...     user_id="company_456",
        ...     filename="invoice_2024_11.pdf",
        ...     file_size=256000,
        ...     storage_path="documents/company_456/invoices/doc_ghi789.pdf",
        ...     content_type="application/pdf",
        ...     metadata={"category": "invoice", "amount": 1500.00, "month": "2024-11"}
        ... )
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "doc_abc123",
                "user_id": "user_123",
                "filename": "contract.pdf",
                "file_size": 524288,
                "upload_date": "2025-11-18T14:30:00Z",
                "storage_path": "documents/user_123/2024/doc_abc123.pdf",
                "content_type": "application/pdf",
                "checksum": "sha256:abc123...",
                "metadata": {"category": "legal", "year": 2024, "tags": ["important"]},
            }
        }
    )

    id: str = Field(..., description="Unique document identifier")
    user_id: str = Field(..., description="User who owns this document")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes", ge=0)
    upload_date: datetime = Field(
        default_factory=datetime.utcnow, description="Upload timestamp (UTC)"
    )
    storage_path: str = Field(..., description="Storage backend path/key")
    content_type: str = Field(..., description="MIME type (e.g., application/pdf)")
    checksum: Optional[str] = Field(
        None, description="File checksum for integrity validation (e.g., sha256:...)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible metadata for custom fields (category, tags, dates, etc.)",
    )
