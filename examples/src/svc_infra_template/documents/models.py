"""Document models using svc-infra base structures.

These models demonstrate how to use svc-infra's document storage
with custom metadata for your application domain.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentCategory(str, Enum):
    """Document categories for organization."""

    CONTRACT = "contract"
    INVOICE = "invoice"
    REPORT = "report"
    MEMO = "memo"
    OTHER = "other"


class DocumentMetadata(BaseModel):
    """Custom metadata for document tagging and search."""

    category: DocumentCategory = Field(..., description="Document category")
    tags: list[str] = Field(default_factory=list, description="Search tags")
    department: str | None = Field(None, description="Department/team")
    project: str | None = Field(None, description="Related project")
    year: int | None = Field(None, description="Document year")


class DocumentUploadRequest(BaseModel):
    """Request to upload a new document."""

    user_id: str = Field(..., description="User uploading the document")
    filename: str = Field(..., description="Original filename")
    content: str = Field(..., description="File content (base64 or text)")
    category: DocumentCategory = Field(..., description="Document category")
    tags: list[str] = Field(default_factory=list, description="Search tags")
    department: str | None = Field(None, description="Department/team")
    project: str | None = Field(None, description="Related project")
    year: int | None = Field(None, description="Document year")


class DocumentResponse(BaseModel):
    """Document response with metadata."""

    id: str = Field(..., description="Document ID")
    user_id: str = Field(..., description="Document owner")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    storage_path: str = Field(..., description="Storage path")
    category: DocumentCategory = Field(..., description="Document category")
    tags: list[str] = Field(default_factory=list, description="Search tags")
    department: str | None = Field(None, description="Department/team")
    project: str | None = Field(None, description="Related project")
    year: int | None = Field(None, description="Document year")
    uploaded_at: datetime = Field(..., description="Upload timestamp")

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}
