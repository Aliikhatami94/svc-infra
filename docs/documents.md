# Generic Document Management

**Status**: ✅ Stable (v1)  
**Module**: `svc_infra.documents`

Generic document storage and metadata management that works with any storage backend (S3, local, memory). Domain-agnostic design allows extension for specific use cases (financial documents, medical records, legal contracts, etc.).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Extension Pattern](#extension-pattern)
- [Production Recommendations](#production-recommendations)
- [Troubleshooting](#troubleshooting)

---

## Overview

The documents module provides:

- **Generic Document Model**: Flexible metadata schema for any document type
- **Storage Integration**: Uses svc-infra storage backend (S3, local, memory)
- **FastAPI Endpoints**: 4 protected routes for upload, get, list, delete
- **Async-First**: Full async/await support for high performance
- **User Isolation**: Built-in user scoping for multi-tenant applications
- **Extensible**: Base layer for domain-specific features (OCR, AI analysis, etc.)

### What It Does NOT Include

- Domain-specific logic (tax forms, medical records, etc.)
- OCR or text extraction
- AI-powered analysis
- File format conversion
- Virus scanning (integrate ClamAV separately)

For domain-specific features, see [Extension Pattern](#extension-pattern) below.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                    │
│              (FastAPI Routes with Auth)                 │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              svc_infra.documents                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   models.py  │  │  storage.py  │  │    add.py    │ │
│  │  (Document)  │  │   (CRUD)     │  │  (FastAPI)   │ │
│  └──────────────┘  └──────┬───────┘  └──────────────┘ │
│                            │                            │
│  ┌──────────────┐  ┌──────▼───────┐                   │
│  │   ease.py    │  │ Metadata DB  │                   │
│  │ (Manager)    │  │ (in-memory)  │                   │
│  └──────────────┘  └──────────────┘                   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              svc_infra.storage                          │
│         (S3, Local, Memory backends)                    │
└─────────────────────────────────────────────────────────┘
```

### Component Overview

| Component | Purpose | Status |
|-----------|---------|--------|
| `models.py` | Document metadata schema | ✅ Stable |
| `storage.py` | CRUD operations | ✅ Stable (in-memory metadata) |
| `add.py` | FastAPI integration | ✅ Stable (protected routes) |
| `ease.py` | DocumentManager helper | ✅ Stable |
| Metadata DB | SQL persistence | 🚧 Coming soon |

---

## Quick Start

### 1. Basic Usage (Programmatic)

```python
import asyncio
from svc_infra.documents import easy_documents

async def main():
    # Create manager (auto-detects storage backend)
    manager = easy_documents()

    # Upload document
    doc = await manager.upload(
        user_id="user_123",
        file=b"PDF content here",
        filename="contract.pdf",
        metadata={"category": "legal", "year": 2024}
    )
    print(f"Uploaded: {doc.id}")

    # List documents
    docs = manager.list(user_id="user_123")
    print(f"Found {len(docs)} documents")

    # Download document
    file_data = await manager.download(doc.id)

    # Delete document
    await manager.delete(doc.id)

asyncio.run(main())
```

### 2. FastAPI Integration

```python
from fastapi import FastAPI
from svc_infra.documents import add_documents

app = FastAPI()

# Add document endpoints (protected, requires auth)
manager = add_documents(app)

# Routes available at:
# - POST /documents/upload
# - GET /documents/{document_id}
# - GET /documents/list?user_id=...
# - DELETE /documents/{document_id}
```

### 3. Upload via HTTP

```bash
# Upload document
curl -X POST http://localhost:8000/documents/upload \
  -F "user_id=user_123" \
  -F "file=@contract.pdf" \
  -F "category=legal" \
  -F "tags=important,2024"

# List documents
curl "http://localhost:8000/documents/list?user_id=user_123"

# Get document metadata
curl http://localhost:8000/documents/doc_abc123

# Delete document
curl -X DELETE http://localhost:8000/documents/doc_abc123
```

---

## Configuration

Documents module inherits storage backend configuration. See [storage.md](./storage.md) for details.

### Environment Variables

```bash
# Storage backend (auto-detected if not set)
STORAGE_BACKEND=s3  # s3, local, memory

# S3 backend
STORAGE_S3_BUCKET=my-documents
STORAGE_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Local backend
STORAGE_BASE_PATH=/data/uploads
STORAGE_BASE_URL=http://localhost:8000/files

# Railway (auto-detected)
RAILWAY_VOLUME_MOUNT_PATH=/data
```

### Custom Storage Backend

```python
from svc_infra.storage import easy_storage
from svc_infra.documents import easy_documents

# Explicit storage backend
storage = easy_storage(backend="s3")
manager = easy_documents(storage)
```

---

## API Reference

### Document Model

```python
from svc_infra.documents import Document

doc = Document(
    id="doc_abc123",
    user_id="user_123",
    filename="contract.pdf",
    file_size=524288,
    upload_date=datetime.utcnow(),
    storage_path="documents/user_123/doc_abc123/contract.pdf",
    content_type="application/pdf",
    checksum="sha256:...",
    metadata={"category": "legal", "year": 2024}
)
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique document identifier (e.g., `doc_abc123`) |
| `user_id` | str | Owner of the document |
| `filename` | str | Original filename |
| `file_size` | int | File size in bytes |
| `upload_date` | datetime | Upload timestamp (UTC) |
| `storage_path` | str | Storage backend key |
| `content_type` | str | MIME type (e.g., `application/pdf`) |
| `checksum` | str | SHA-256 hash for integrity |
| `metadata` | dict | Flexible custom metadata |

### Storage Operations

```python
from svc_infra.documents.storage import (
    upload_document,
    get_document,
    download_document,
    delete_document,
    list_documents,
)

# Upload
doc = await upload_document(
    storage=storage,
    user_id="user_123",
    file=file_bytes,
    filename="document.pdf",
    metadata={"category": "legal"},
    content_type="application/pdf"  # optional, auto-detected
)

# Get metadata
doc = get_document("doc_abc123")

# Download file
file_bytes = await download_document(storage, "doc_abc123")

# Delete
success = await delete_document(storage, "doc_abc123")

# List
docs = list_documents(user_id="user_123", limit=100, offset=0)
```

### DocumentManager

```python
from svc_infra.documents import DocumentManager, easy_documents

# Create manager
manager = easy_documents()  # or DocumentManager(storage)

# Upload
doc = await manager.upload(user_id, file, filename, metadata, content_type)

# Get
doc = manager.get(document_id)

# Download
file_bytes = await manager.download(document_id)

# Delete
success = await manager.delete(document_id)

# List
docs = manager.list(user_id, limit=100, offset=0)
```

### FastAPI Integration

```python
from svc_infra.documents import add_documents

# Add to app
manager = add_documents(
    app,
    storage_backend=None,  # auto-detect
    prefix="/documents",
    tags=["Documents"]
)

# Programmatic access
doc = await manager.upload(...)
```

---

## Examples

### Example 1: Legal Document Management

```python
import asyncio
from svc_infra.documents import easy_documents

async def upload_contract(user_id: str, file_path: str):
    manager = easy_documents()

    with open(file_path, "rb") as f:
        file_content = f.read()

    doc = await manager.upload(
        user_id=user_id,
        file=file_content,
        filename="employment_contract.pdf",
        metadata={
            "category": "legal",
            "type": "employment_contract",
            "signed_date": "2024-11-18",
            "parties": ["Company Inc", "John Doe"],
            "status": "active"
        }
    )

    return doc

asyncio.run(upload_contract("user_123", "contract.pdf"))
```

### Example 2: Search by Metadata

```python
def search_documents_by_category(user_id: str, category: str):
    """Search documents by metadata category."""
    manager = easy_documents()

    # Get all user's documents
    all_docs = manager.list(user_id)

    # Filter by metadata
    filtered = [
        doc for doc in all_docs
        if doc.metadata.get("category") == category
    ]

    return filtered

# Find all legal documents
legal_docs = search_documents_by_category("user_123", "legal")
```

### Example 3: Batch Upload

```python
import asyncio
from pathlib import Path
from svc_infra.documents import easy_documents

async def batch_upload(user_id: str, folder_path: str):
    """Upload all files from a folder."""
    manager = easy_documents()
    uploaded = []

    for file_path in Path(folder_path).glob("*"):
        if file_path.is_file():
            with open(file_path, "rb") as f:
                doc = await manager.upload(
                    user_id=user_id,
                    file=f.read(),
                    filename=file_path.name,
                    metadata={"batch": "2024-11", "source": folder_path}
                )
                uploaded.append(doc)

    return uploaded

docs = asyncio.run(batch_upload("user_123", "./contracts"))
print(f"Uploaded {len(docs)} documents")
```

### Example 4: Document Expiration

```python
from datetime import datetime, timedelta
from svc_infra.documents import easy_documents

async def cleanup_expired_documents(user_id: str, days: int = 90):
    """Delete documents older than specified days."""
    manager = easy_documents()

    # Get all documents
    docs = manager.list(user_id)

    # Find expired
    cutoff = datetime.utcnow() - timedelta(days=days)
    expired = [doc for doc in docs if doc.upload_date < cutoff]

    # Delete
    for doc in expired:
        await manager.delete(doc.id)
        print(f"Deleted expired document: {doc.filename}")

    return len(expired)
```

---

## Extension Pattern

The documents module is designed as a **base layer** for domain-specific extensions. Here's how to extend it:

### Example: Financial Documents (fin-infra)

```python
# fin-infra/src/fin_infra/documents/models.py
from svc_infra.documents import Document as BaseDocument
from enum import Enum

class DocumentType(str, Enum):
    """Financial document types."""
    TAX = "tax"
    STATEMENT = "statement"
    RECEIPT = "receipt"

class FinancialDocument(BaseDocument):
    """Extends base with financial fields."""
    type: DocumentType
    tax_year: int
    form_type: str  # W-2, 1099, etc.

class OCRResult(BaseModel):
    """OCR extraction result."""
    document_id: str
    text: str
    fields_extracted: dict
    confidence: float
```

```python
# fin-infra/src/fin_infra/documents/ocr.py
from svc_infra.documents import download_document
from ai_infra.llm import CoreLLM

async def extract_text(document_id: str) -> OCRResult:
    """Extract text from financial documents."""
    # Use svc-infra to download file
    file_data = await download_document(storage, document_id)

    # Financial-specific OCR logic
    if form_type == "W-2":
        return extract_w2_fields(file_data)
    # ...
```

```python
# fin-infra/src/fin_infra/documents/add.py
from svc_infra.documents import add_documents as add_base_documents

def add_financial_documents(app):
    """Add financial document endpoints."""
    # First, add base endpoints
    add_base_documents(app)

    # Then add financial-specific endpoints
    router = user_router(prefix="/documents", tags=["Financial"])

    @router.post("/{doc_id}/ocr")
    async def extract_text_endpoint(doc_id: str):
        return await extract_text(doc_id)

    app.include_router(router)
```

### Other Domain Examples

**Medical Records**:
```python
class MedicalDocument(Document):
    patient_id: str
    record_type: str  # lab_result, prescription, imaging
    provider: str
    visit_date: date
```

**Legal Contracts**:
```python
class LegalDocument(Document):
    contract_type: str
    parties: list[str]
    effective_date: date
    expiration_date: date
    status: str  # draft, active, expired
```

**E-commerce**:
```python
class ProductDocument(Document):
    product_id: str
    doc_type: str  # manual, warranty, certification
    language: str
```

---

## Production Recommendations

### Storage Backend

- **Development**: Use `MemoryBackend` (no setup required)
- **Railway/Render**: Use `LocalBackend` with persistent volumes
- **AWS**: Use `S3Backend` with dedicated bucket
- **DigitalOcean**: Use `S3Backend` with Spaces endpoint
- **Multi-region**: Use `S3Backend` with replication

### Metadata Storage

**Current**: In-memory dictionary (ephemeral)

**Production** (coming soon): SQL database integration
```python
# Future API
from svc_infra.documents import add_documents
from svc_infra.db import get_engine

manager = add_documents(
    app,
    storage_backend=storage,
    metadata_engine=get_engine()  # Use SQL for persistence
)
```

### File Validation

```python
from svc_infra.documents import easy_documents

async def upload_with_validation(user_id: str, file: bytes, filename: str):
    # Validate file size (10MB limit)
    if len(file) > 10 * 1024 * 1024:
        raise ValueError("File too large (max 10MB)")

    # Validate file type
    allowed_types = {"application/pdf", "image/jpeg", "image/png"}
    content_type = guess_type(filename)
    if content_type not in allowed_types:
        raise ValueError(f"File type not allowed: {content_type}")

    # Upload
    manager = easy_documents()
    return await manager.upload(user_id, file, filename)
```

### User Quotas

```python
def check_user_quota(user_id: str, max_documents: int = 1000):
    """Enforce per-user document limits."""
    manager = easy_documents()
    docs = manager.list(user_id)

    if len(docs) >= max_documents:
        raise ValueError(f"User quota exceeded ({max_documents} documents)")
```

### Security Considerations

1. **Authentication**: All routes use protected `user_router` (requires auth)
2. **User Isolation**: Documents are scoped to `user_id`
3. **File Integrity**: SHA-256 checksums prevent tampering
4. **Storage Security**: Inherit from storage backend (S3 encryption, signed URLs)

**Additional Recommendations**:
- Validate file content (not just extension)
- Integrate virus scanning (ClamAV)
- Add rate limiting on upload endpoint
- Enable audit logging (track who accessed what)
- Use signed URLs for downloads (prevent hotlinking)

---

## Troubleshooting

### Problem: "Documents not configured" Error

```python
RuntimeError: Documents not configured. Call add_documents(app) first.
```

**Solution**: Call `add_documents(app)` during app initialization:

```python
from fastapi import FastAPI
from svc_infra.documents import add_documents

app = FastAPI()
add_documents(app)  # Must be called before routes are accessed
```

### Problem: Storage Backend Not Found

```
FileNotFoundError: Storage backend not configured
```

**Solution**: Configure storage backend explicitly or set environment variables:

```python
# Option 1: Explicit backend
from svc_infra.storage import easy_storage
storage = easy_storage(backend="local")
manager = easy_documents(storage)

# Option 2: Environment variables
export STORAGE_BACKEND=s3
export STORAGE_S3_BUCKET=my-bucket
```

### Problem: Metadata Not Persisting

**Symptom**: Documents disappear after app restart

**Cause**: Current implementation uses in-memory metadata storage

**Solution**: Wait for SQL metadata integration (coming soon) or implement custom persistence:

```python
import json

def save_metadata_to_disk():
    """Temporary workaround: serialize to JSON."""
    from svc_infra.documents.storage import _documents_metadata

    with open("documents_metadata.json", "w") as f:
        json.dump({k: v.dict() for k, v in _documents_metadata.items()}, f)
```

### Problem: Async/Await Errors

```python
TypeError: object bytes can't be used in 'await' expression
```

**Cause**: Mixing sync and async code

**Solution**: Ensure all document operations use `await`:

```python
# ❌ Wrong
doc = manager.upload(user_id, file, filename)

# ✅ Correct
doc = await manager.upload(user_id, file, filename)
```

### Problem: Large File Upload Timeouts

**Solution**: Adjust FastAPI body size limits and timeouts:

```python
from fastapi import FastAPI
from svc_infra.documents import add_documents

app = FastAPI()
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_size=100 * 1024 * 1024  # 100MB
)
add_documents(app)
```

---

## Next Steps

- [ ] Add SQL metadata persistence (replace in-memory dict)
- [ ] Add search by metadata filters
- [ ] Add document versioning
- [ ] Add bulk operations (batch upload/delete)
- [ ] Add document sharing (between users)
- [ ] Add document retention policies

---

## See Also

- [Storage System](./storage.md) - Backend configuration
- [API Scaffolding](./api.md) - FastAPI integration patterns
- [Security](./security.md) - Authentication and RBAC
- [Acceptance Matrix](./acceptance-matrix.md) - Test scenarios
