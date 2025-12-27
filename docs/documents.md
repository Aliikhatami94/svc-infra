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
from ai_infra.llm import LLM

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

---

## AI Integration (Coming Soon)

> **Status**: Planned integration with ai-infra for document processing

svc-infra's document module is designed to integrate seamlessly with ai-infra for AI-powered document processing. While these features are in development, here's the planned architecture:

### OCR Integration

Extract text from images and PDFs using ai-infra's vision capabilities:

```python
# Planned API
from svc_infra.documents import DocumentManager
from ai_infra.llm import LLM

async def extract_text_from_document(doc_id: str) -> str:
    """Extract text from document using OCR."""
    manager = easy_documents()

    # Download document
    file_bytes = await manager.download(doc_id)
    doc = manager.get(doc_id)

    # Use ai-infra vision model for OCR
    llm = LLM(model="gpt-4o")  # Vision-capable model

    if doc.content_type.startswith("image/"):
        # Direct image OCR
        result = await llm.generate(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text from this image. Return only the extracted text, no commentary."},
                    {"type": "image", "data": file_bytes}
                ]
            }]
        )
        return result.text

    elif doc.content_type == "application/pdf":
        # PDF: Extract pages as images, OCR each
        from pdf2image import convert_from_bytes
        pages = convert_from_bytes(file_bytes)

        extracted_text = []
        for i, page in enumerate(pages):
            page_bytes = page_to_bytes(page)
            result = await llm.generate(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Extract all text from page {i+1}. Return only the extracted text."},
                        {"type": "image", "data": page_bytes}
                    ]
                }]
            )
            extracted_text.append(result.text)

        return "\n\n---\n\n".join(extracted_text)

    else:
        raise ValueError(f"Unsupported content type for OCR: {doc.content_type}")
```

### Document Classification

Automatically classify documents using AI:

```python
# Planned API
from pydantic import BaseModel
from ai_infra.llm import LLM

class DocumentClassification(BaseModel):
    """Document classification result."""
    category: str  # invoice, receipt, contract, report, letter, etc.
    subcategory: str | None
    language: str  # ISO 639-1 code
    confidence: float  # 0.0 - 1.0

async def classify_document(doc_id: str) -> DocumentClassification:
    """Classify document type using AI."""
    manager = easy_documents()

    # Get document content (via OCR if needed)
    text = await extract_text_from_document(doc_id)

    # Use structured output for classification
    llm = LLM(model="gpt-4o-mini")

    result = await llm.generate(
        messages=[{
            "role": "user",
            "content": f"""Classify this document:

{text[:4000]}

Provide:
- category: The document type (invoice, receipt, contract, report, letter, form, manual, other)
- subcategory: More specific type if applicable
- language: ISO 639-1 language code (e.g., "en", "es", "fr")
- confidence: Your confidence score (0.0 to 1.0)"""
        }],
        response_format=DocumentClassification
    )

    return result.parsed
```

### Entity Extraction

Extract structured data from documents:

```python
# Planned API
from pydantic import BaseModel

class InvoiceData(BaseModel):
    """Extracted invoice data."""
    vendor_name: str
    invoice_number: str
    invoice_date: str
    due_date: str | None
    total_amount: float
    currency: str
    line_items: list[dict]

async def extract_invoice_data(doc_id: str) -> InvoiceData:
    """Extract structured data from invoice document."""
    text = await extract_text_from_document(doc_id)

    llm = LLM(model="gpt-4o")

    result = await llm.generate(
        messages=[{
            "role": "user",
            "content": f"""Extract invoice data from this document:

{text}

Extract all relevant fields. For line_items, include description, quantity, unit_price, and total for each item."""
        }],
        response_format=InvoiceData
    )

    return result.parsed
```

### Semantic Search Integration

Index documents for semantic search with ai-infra Retriever:

```python
# Planned API
from ai_infra import Retriever
from svc_infra.documents import easy_documents

async def index_documents_for_search(user_id: str, retriever: Retriever):
    """Index all user documents for semantic search."""
    manager = easy_documents()
    docs = manager.list(user_id)

    for doc in docs:
        # Extract text (OCR if needed)
        text = await extract_text_from_document(doc.id)

        # Add to retriever with metadata
        retriever.add_text(
            text,
            metadata={
                "source": f"document://{doc.id}",
                "document_id": doc.id,
                "filename": doc.filename,
                "user_id": doc.user_id,
                "upload_date": doc.upload_date.isoformat(),
                **doc.metadata
            }
        )

    return len(docs)

async def search_documents(
    user_id: str,
    query: str,
    retriever: Retriever,
    limit: int = 10
) -> list[dict]:
    """Search user's documents semantically."""
    results = retriever.search(
        query,
        filter={"user_id": user_id},
        limit=limit
    )

    # Enrich with document metadata
    manager = easy_documents()
    enriched = []

    for result in results:
        doc_id = result.metadata.get("document_id")
        if doc_id:
            doc = manager.get(doc_id)
            enriched.append({
                "document": doc,
                "snippet": result.text[:500],
                "score": result.score
            })

    return enriched
```

### Document Summarization

Generate summaries of documents:

```python
# Planned API
async def summarize_document(
    doc_id: str,
    max_length: int = 500,
    style: str = "concise"  # concise, detailed, bullet_points
) -> str:
    """Generate a summary of the document."""
    text = await extract_text_from_document(doc_id)

    llm = LLM(model="gpt-4o-mini")

    style_prompts = {
        "concise": f"Summarize in {max_length} characters or less:",
        "detailed": f"Provide a detailed summary (max {max_length} chars):",
        "bullet_points": f"Summarize as bullet points (max {max_length} chars):"
    }

    result = await llm.generate(
        messages=[{
            "role": "user",
            "content": f"""{style_prompts.get(style, style_prompts['concise'])}

{text}"""
        }]
    )

    return result.text

# Store summary in metadata
async def summarize_and_store(doc_id: str):
    """Summarize document and store in metadata."""
    summary = await summarize_document(doc_id)

    # Update document metadata
    manager = easy_documents()
    doc = manager.get(doc_id)
    doc.metadata["ai_summary"] = summary
    doc.metadata["summarized_at"] = datetime.utcnow().isoformat()

    return summary
```

### Batch Processing Pipeline

Process documents in batch with rate limiting:

```python
# Planned API
import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")

async def process_documents_batch(
    doc_ids: list[str],
    processor: Callable[[str], T],
    *,
    concurrency: int = 5,
    delay_seconds: float = 0.1
) -> list[T | Exception]:
    """Process documents in batch with rate limiting."""
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def process_one(doc_id: str) -> T | Exception:
        async with semaphore:
            try:
                result = await processor(doc_id)
                await asyncio.sleep(delay_seconds)  # Rate limiting
                return result
            except Exception as e:
                return e

    tasks = [process_one(doc_id) for doc_id in doc_ids]
    results = await asyncio.gather(*tasks)

    return results

# Usage
async def batch_classify():
    manager = easy_documents()
    docs = manager.list("user_123")
    doc_ids = [doc.id for doc in docs]

    results = await process_documents_batch(
        doc_ids,
        classify_document,
        concurrency=3  # Limit concurrent AI calls
    )

    for doc_id, result in zip(doc_ids, results):
        if isinstance(result, Exception):
            print(f"Failed to classify {doc_id}: {result}")
        else:
            print(f"{doc_id}: {result.category}")
```

### Integration with fin-infra

For financial documents, fin-infra provides specialized extractors:

```python
# fin-infra extension pattern
from fin_infra.documents import (
    extract_w2_data,
    extract_1099_data,
    extract_bank_statement,
    extract_receipt,
)

# Specialized extractors with financial validation
w2_data = await extract_w2_data(doc_id)  # Validates SSN format, amounts, etc.
receipt = await extract_receipt(doc_id)   # Extracts vendor, items, tax, total

# See fin-infra documentation for details
```

---

## Webhook Notifications

Configure webhooks to receive document events:

```python
# Planned API
from svc_infra.documents import DocumentManager
from svc_infra.webhooks import WebhookConfig

async def setup_document_webhooks(app, webhook_url: str):
    """Configure webhooks for document events."""
    manager = add_documents(app)

    # Configure webhook notifications
    webhook_config = WebhookConfig(
        url=webhook_url,
        events=["document.uploaded", "document.deleted", "document.processed"],
        secret="webhook-signing-secret"
    )

    # Hook into manager events
    original_upload = manager.upload

    async def upload_with_webhook(*args, **kwargs):
        doc = await original_upload(*args, **kwargs)

        # Send webhook
        await send_webhook(webhook_config, {
            "event": "document.uploaded",
            "document_id": doc.id,
            "filename": doc.filename,
            "user_id": doc.user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        return doc

    manager.upload = upload_with_webhook
```

### Event Payloads

| Event | Payload |
|-------|---------|
| `document.uploaded` | `{document_id, filename, user_id, content_type, file_size}` |
| `document.deleted` | `{document_id, filename, user_id}` |
| `document.processed` | `{document_id, processing_type, result}` |
| `document.shared` | `{document_id, shared_with, permissions}` |

---

## Audit Logging

Track document access and modifications:

```python
# Planned API
from svc_infra.documents import DocumentManager
from svc_infra.audit import AuditLog

class AuditedDocumentManager(DocumentManager):
    """Document manager with audit logging."""

    def __init__(self, storage, audit_log: AuditLog):
        super().__init__(storage)
        self.audit = audit_log

    async def upload(self, user_id: str, file: bytes, filename: str, **kwargs):
        doc = await super().upload(user_id, file, filename, **kwargs)

        await self.audit.log({
            "action": "document.upload",
            "actor_id": user_id,
            "resource_type": "document",
            "resource_id": doc.id,
            "details": {
                "filename": filename,
                "size": len(file),
                "content_type": doc.content_type
            }
        })

        return doc

    async def download(self, document_id: str, *, actor_id: str = None):
        file_bytes = await super().download(document_id)

        await self.audit.log({
            "action": "document.download",
            "actor_id": actor_id,
            "resource_type": "document",
            "resource_id": document_id,
        })

        return file_bytes

    async def delete(self, document_id: str, *, actor_id: str = None):
        doc = self.get(document_id)
        success = await super().delete(document_id)

        if success:
            await self.audit.log({
                "action": "document.delete",
                "actor_id": actor_id,
                "resource_type": "document",
                "resource_id": document_id,
                "details": {"filename": doc.filename}
            })

        return success
```

### Audit Log Schema

```sql
CREATE TABLE document_audit_log (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action VARCHAR(50) NOT NULL,       -- document.upload, document.download, etc.
    actor_id VARCHAR(100),             -- User who performed action
    resource_id VARCHAR(100) NOT NULL, -- Document ID
    details JSONB,                     -- Additional context
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_audit_document ON document_audit_log(resource_id);
CREATE INDEX idx_audit_actor ON document_audit_log(actor_id);
CREATE INDEX idx_audit_timestamp ON document_audit_log(timestamp DESC);
```

---

## Virus Scanning

Integrate virus scanning for uploaded documents:

```python
# Planned API
import clamd  # ClamAV client

class VirusScanningDocumentManager(DocumentManager):
    """Document manager with virus scanning."""

    def __init__(self, storage, clamav_socket: str = "/var/run/clamav/clamd.sock"):
        super().__init__(storage)
        self.scanner = clamd.ClamdUnixSocket(clamav_socket)

    async def upload(self, user_id: str, file: bytes, filename: str, **kwargs):
        # Scan file before upload
        scan_result = self.scanner.instream(file)

        if scan_result["stream"][0] == "FOUND":
            virus_name = scan_result["stream"][1]
            raise ValueError(f"Virus detected: {virus_name}")

        # Safe to upload
        return await super().upload(user_id, file, filename, **kwargs)

# Environment setup
# 1. Install ClamAV: apt-get install clamav clamav-daemon
# 2. Start daemon: systemctl start clamav-daemon
# 3. Install Python client: pip install pyclamd
```

### Scanning Results

| Result | Action |
|--------|--------|
| `OK` | Proceed with upload |
| `FOUND` | Reject upload, log incident |
| `ERROR` | Log warning, allow upload (fail-open) or reject (fail-closed) |

---

## Document Retention Policies

Implement automatic document retention and deletion:

```python
# Planned API
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class RetentionPolicy:
    """Document retention policy."""
    name: str
    retention_days: int
    applies_to: dict  # Metadata filter
    action: str = "delete"  # delete, archive, notify

# Define policies
policies = [
    RetentionPolicy(
        name="temp_uploads",
        retention_days=7,
        applies_to={"category": "temporary"},
        action="delete"
    ),
    RetentionPolicy(
        name="tax_documents",
        retention_days=365 * 7,  # 7 years
        applies_to={"category": "tax"},
        action="archive"
    ),
    RetentionPolicy(
        name="contracts",
        retention_days=365 * 10,  # 10 years
        applies_to={"category": "legal", "type": "contract"},
        action="notify"  # Notify before deletion
    ),
]

async def apply_retention_policies(policies: list[RetentionPolicy]):
    """Apply retention policies to all documents."""
    manager = easy_documents()

    for policy in policies:
        cutoff = datetime.utcnow() - timedelta(days=policy.retention_days)

        # Find matching documents
        all_docs = manager.list()
        for doc in all_docs:
            # Check if policy applies
            if not matches_filter(doc.metadata, policy.applies_to):
                continue

            # Check if past retention period
            if doc.upload_date >= cutoff:
                continue

            # Apply action
            if policy.action == "delete":
                await manager.delete(doc.id)
                print(f"Deleted {doc.filename} (policy: {policy.name})")

            elif policy.action == "archive":
                await archive_document(doc)
                print(f"Archived {doc.filename} (policy: {policy.name})")

            elif policy.action == "notify":
                await notify_retention(doc, policy)
                print(f"Notified about {doc.filename} (policy: {policy.name})")

# Run daily via cron or scheduler
# 0 2 * * * python -c "from myapp import apply_retention_policies; ..."
```

---

## Version History

Track document versions with change history:

```python
# Planned API
from svc_infra.documents import Document

class DocumentVersion(BaseModel):
    """A specific version of a document."""
    version_id: str
    document_id: str
    version_number: int
    storage_path: str
    created_at: datetime
    created_by: str
    change_summary: str | None

class VersionedDocumentManager(DocumentManager):
    """Document manager with version history."""

    async def upload_version(
        self,
        document_id: str,
        file: bytes,
        *,
        user_id: str,
        change_summary: str = None
    ) -> DocumentVersion:
        """Upload a new version of existing document."""
        doc = self.get(document_id)

        # Get next version number
        versions = self.list_versions(document_id)
        next_version = max(v.version_number for v in versions) + 1 if versions else 1

        # Upload new version
        version_path = f"{doc.storage_path}/v{next_version}"
        await self.storage.upload(file, version_path)

        # Create version record
        version = DocumentVersion(
            version_id=f"ver_{uuid4().hex[:12]}",
            document_id=document_id,
            version_number=next_version,
            storage_path=version_path,
            created_at=datetime.utcnow(),
            created_by=user_id,
            change_summary=change_summary
        )

        # Update document to point to latest version
        doc.storage_path = version_path
        doc.metadata["current_version"] = next_version

        return version

    def list_versions(self, document_id: str) -> list[DocumentVersion]:
        """List all versions of a document."""
        # Implementation depends on metadata storage
        ...

    async def download_version(
        self,
        document_id: str,
        version_number: int
    ) -> bytes:
        """Download a specific version."""
        versions = self.list_versions(document_id)
        version = next(
            (v for v in versions if v.version_number == version_number),
            None
        )

        if not version:
            raise ValueError(f"Version {version_number} not found")

        return await self.storage.download(version.storage_path)

    async def restore_version(
        self,
        document_id: str,
        version_number: int,
        *,
        user_id: str
    ) -> DocumentVersion:
        """Restore a previous version as the current version."""
        old_content = await self.download_version(document_id, version_number)

        return await self.upload_version(
            document_id,
            old_content,
            user_id=user_id,
            change_summary=f"Restored from version {version_number}"
        )
```

### Version Comparison

```python
async def compare_versions(
    document_id: str,
    version_a: int,
    version_b: int
) -> dict:
    """Compare two document versions."""
    manager = VersionedDocumentManager(storage)

    content_a = await manager.download_version(document_id, version_a)
    content_b = await manager.download_version(document_id, version_b)

    # For text documents, show diff
    if document_id_is_text(document_id):
        import difflib
        diff = difflib.unified_diff(
            content_a.decode().splitlines(),
            content_b.decode().splitlines(),
            fromfile=f"v{version_a}",
            tofile=f"v{version_b}"
        )
        return {"type": "text_diff", "diff": "\n".join(diff)}

    # For binary documents, show size comparison
    return {
        "type": "binary",
        "size_a": len(content_a),
        "size_b": len(content_b),
        "size_diff": len(content_b) - len(content_a)
    }
```
