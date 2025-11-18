# ADR 0012: Generic File Storage System

## Status

Proposed — Design phase (2025-11-17)

## Context

svc-infra currently lacks a generic file storage abstraction. Applications built on svc-infra need to store user-uploaded files (profile pictures, documents, media, attachments) with backend flexibility. Current state:

- **svc-infra**: No file storage system exists (only commented references to "use svc-infra storage")
- **fin-infra**: Documents module uses in-memory placeholder dictionaries (`_documents`, `_file_storage`)
- **Applications**: No standard way to store files, forcing each app to implement custom solutions

### Requirements

1. **Backend Agnostic**: Work with ANY storage provider without code changes
   - Local filesystem (Railway persistent volumes, Render, development)
   - S3-compatible (AWS S3, DigitalOcean Spaces, Wasabi, Backblaze B2, Minio)
   - Google Cloud Storage
   - Cloudinary (image optimization)
   - In-memory (testing)

2. **Security First**:
   - Signed URLs with expiration by default
   - No exposure of raw file paths
   - Tenant isolation via key prefixes
   - Metadata validation

3. **Production Ready**:
   - Async operations (non-blocking)
   - Connection pooling
   - Retry logic for transient failures
   - Health checks
   - Observability (metrics, logging)

4. **Developer Experience**:
   - One-line integration via `add_storage(app)`
   - Auto-detection from environment variables
   - Type-safe with Pydantic settings
   - Clear error messages

5. **Separation of Concerns**:
   - **svc-infra/storage/**: Generic file storage infrastructure (reusable)
   - **Domain packages** (fin-infra, etc.): Domain-specific features built ON TOP
   - Example: fin-infra documents keep OCR/AI analysis, delegate storage to svc-infra

## Decisions

### 1. Abstract Storage Backend Interface

Define a protocol-based interface that all backends must implement:

```python
from typing import Protocol, Optional

class StorageBackend(Protocol):
    """Abstract storage backend interface."""

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store file and return public/signed URL."""
        ...

    async def get(self, key: str) -> bytes:
        """Retrieve file content."""
        ...

    async def delete(self, key: str) -> bool:
        """Remove file. Returns True if deleted, False if not found."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if file exists."""
        ...

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
        download: bool = False,
    ) -> str:
        """Generate signed/public URL."""
        ...

    async def list_keys(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> list[str]:
        """List stored file keys with optional prefix filter."""
        ...

    async def get_metadata(self, key: str) -> dict:
        """Get file metadata (size, content_type, custom metadata)."""
        ...
```

**Rationale**: Protocol-based design (PEP 544) allows structural subtyping without inheritance, making it easy to add new backends without modifying existing code.

### 2. Exception Hierarchy

```python
class StorageError(Exception):
    """Base exception for storage operations."""
    pass

class FileNotFoundError(StorageError):
    """Raised when file does not exist."""
    pass

class PermissionDeniedError(StorageError):
    """Raised when lacking permissions for operation."""
    pass

class QuotaExceededError(StorageError):
    """Raised when storage quota is exceeded."""
    pass

class InvalidKeyError(StorageError):
    """Raised when key format is invalid."""
    pass
```

**Rationale**: Specific exceptions enable fine-grained error handling and better user feedback.

### 3. Backend Implementations

#### LocalBackend (Filesystem)

Use cases: Railway persistent volumes, Render disks, local development

```python
class LocalBackend:
    def __init__(
        self,
        base_path: str = "/data/uploads",
        base_url: str = "http://localhost:8000/files",
        signing_secret: Optional[str] = None,
    ):
        self.base_path = Path(base_path)
        self.base_url = base_url
        self.signing_secret = signing_secret or secrets.token_urlsafe(32)
```

Features:
- Async file I/O using `aiofiles`
- HMAC-based URL signing with expiration
- Metadata stored as JSON sidecar files (`{key}.meta.json`)
- Atomic writes using temp files
- Automatic directory creation

**Railway Integration**: Detects `RAILWAY_VOLUME_MOUNT_PATH` and uses it as base_path

#### S3Backend (S3-Compatible)

Use cases: AWS S3, DigitalOcean Spaces, Wasabi, Backblaze B2, Minio

```python
class S3Backend:
    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        self.bucket = bucket
        self.region = region
        self.endpoint = endpoint  # For DigitalOcean, Wasabi, etc.
```

Features:
- Uses `aioboto3` for async operations
- Custom endpoint support for S3-compatible services
- Presigned URLs with configurable expiration
- Multipart upload for large files (>5MB)
- Connection pooling
- Metadata stored in S3 object metadata
- Retry logic with exponential backoff

**DigitalOcean Spaces Example**:
```python
S3Backend(
    bucket="my-uploads",
    region="nyc3",
    endpoint="https://nyc3.digitaloceanspaces.com",
)
```

#### MemoryBackend (In-Memory)

Use cases: Unit tests, development, temporary storage

```python
class MemoryBackend:
    def __init__(self, max_size: int = 100_000_000):  # 100MB default
        self._storage: dict[str, bytes] = {}
        self._metadata: dict[str, dict] = {}
        self.max_size = max_size
```

Features:
- Dictionary-based storage
- Thread-safe operations using `asyncio.Lock`
- TTL support for automatic expiration
- Size limits
- No persistence across restarts

#### GCSBackend (Google Cloud Storage) - Optional for v1

Use cases: Google Cloud Platform deployments

```python
class GCSBackend:
    def __init__(
        self,
        bucket: str,
        project: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        self.bucket = bucket
        self.project = project
```

Features:
- Uses `google-cloud-storage` SDK
- Async wrapper around sync SDK
- Signed URLs with service account
- Metadata in GCS object metadata

**Defer to fast-follow** if time constrained for v1.

#### CloudinaryBackend (Image Optimization) - Optional for v1

Use cases: Image-heavy applications, automatic optimization

```python
class CloudinaryBackend:
    def __init__(
        self,
        cloud_name: str,
        api_key: str,
        api_secret: str,
    ):
        self.cloud_name = cloud_name
```

Features:
- Uses `cloudinary` SDK
- Automatic image optimization
- URL transformations (resize, crop, format)
- CDN delivery

**Defer to fast-follow** if time constrained for v1.

### 4. Configuration and Auto-Detection

Use Pydantic settings with environment variables:

```python
class StorageSettings(BaseSettings):
    # Backend selection
    storage_backend: Optional[str] = None  # "local", "s3", "gcs", "cloudinary", "memory"

    # Local backend
    storage_base_path: str = "/data/uploads"
    storage_base_url: str = "http://localhost:8000/files"
    storage_signing_secret: Optional[str] = None

    # S3 backend
    storage_s3_bucket: Optional[str] = None
    storage_s3_region: str = "us-east-1"
    storage_s3_endpoint: Optional[str] = None
    storage_s3_access_key: Optional[str] = None
    storage_s3_secret_key: Optional[str] = None

    # GCS backend
    storage_gcs_bucket: Optional[str] = None
    storage_gcs_project: Optional[str] = None
    storage_gcs_credentials_path: Optional[str] = None

    # Cloudinary backend
    storage_cloudinary_cloud_name: Optional[str] = None
    storage_cloudinary_api_key: Optional[str] = None
    storage_cloudinary_api_secret: Optional[str] = None

    class Config:
        env_file = ".env"
```

**Auto-Detection Logic** (when `storage_backend` not explicitly set):

1. Check for Railway: `RAILWAY_VOLUME_MOUNT_PATH` exists → LocalBackend
2. Check for S3: `AWS_ACCESS_KEY_ID` or `storage_s3_bucket` set → S3Backend
3. Check for GCS: `GOOGLE_APPLICATION_CREDENTIALS` or `storage_gcs_bucket` set → GCSBackend
4. Check for Cloudinary: `CLOUDINARY_URL` set → CloudinaryBackend
5. Default: MemoryBackend (with warning log)

**Rationale**: Zero-config for common platforms (Railway, AWS) while allowing explicit override.

### 5. FastAPI Integration Pattern

```python
from svc_infra.storage import add_storage, easy_storage

# Option 1: Auto-detect backend
storage = easy_storage()
add_storage(app, storage)

# Option 2: Explicit backend
storage = easy_storage(backend="s3", bucket="my-uploads")
add_storage(app, storage)

# Option 3: Custom backend instance
from svc_infra.storage.backends import S3Backend
storage = S3Backend(bucket="my-uploads", region="us-west-2")
add_storage(app, storage)
```

The `add_storage` helper:
- Stores backend in `app.state.storage`
- Registers startup hook for connection testing
- Registers shutdown hook for cleanup
- Adds health check endpoint (`/_health/storage`)
- Optionally mounts file serving route (`/files/{path:path}`)

Dependency injection in routes:

```python
from svc_infra.storage import get_storage
from fastapi import Depends, UploadFile

@router.post("/avatar")
async def upload_avatar(
    file: UploadFile,
    storage: StorageBackend = Depends(get_storage),
):
    content = await file.read()
    url = await storage.put(
        key=f"avatars/{user_id}/{file.filename}",
        data=content,
        content_type=file.content_type,
        metadata={"user_id": user_id},
    )
    return {"url": url}
```

### 6. Key Naming Conventions

Support tenant-scoped and resource-scoped keys:

```
{tenant_id}/{resource_type}/{resource_id}/{filename}
```

Examples:
- `tenant_123/avatars/user_456/profile.jpg`
- `tenant_123/documents/doc_789/invoice.pdf`
- `public/logos/company-logo.png` (no tenant isolation)

**Validation**: Keys must be:
- Relative paths (no leading `/`)
- No `..` path traversal
- Max 1024 characters
- Safe characters: `a-zA-Z0-9._-/`

### 7. Security Considerations

1. **Signed URLs by Default**: All URLs should have expiration (default 1 hour)
2. **No Raw Path Exposure**: Never expose filesystem paths or S3 keys directly
3. **Content-Type Validation**: Validate MIME types before storage
4. **Size Limits**: Enforce max file size (default 10MB, configurable)
5. **Virus Scanning**: Hook for integration (ClamAV, VirusTotal) - defer to fast-follow
6. **Tenant Isolation**: Enforce key prefixes, prevent cross-tenant access
7. **Rate Limiting**: Apply to upload endpoints

### 8. Observability

Metrics (Prometheus):
```
storage_operations_total{backend, operation, status}
storage_operation_duration_seconds{backend, operation}
storage_file_size_bytes{backend}
storage_errors_total{backend, error_type}
```

Logging:
- Info: File uploaded/deleted with key and size
- Error: Operation failures with backend and error details
- Debug: URL generation, metadata operations

### 9. Migration Path

For existing applications using placeholder storage (like fin-infra documents):

1. **Add svc-infra storage dependency**
2. **Configure backend via environment variables**
3. **Replace direct storage calls with svc-infra storage**
4. **Keep domain-specific logic** (OCR, analysis, retention policies)
5. **Test with MemoryBackend first**, then switch to production backend
6. **Migrate existing files** (one-time script to copy from old storage to new)

Example refactor for fin-infra documents:

```python
# Before (in-memory)
_file_storage: Dict[str, bytes] = {}

def download_document(doc_id: str) -> bytes:
    return _file_storage[doc_id]

# After (svc-infra storage)
from svc_infra.storage import get_storage

async def download_document(doc_id: str, storage: StorageBackend) -> bytes:
    return await storage.get(f"documents/{doc_id}")
```

### 10. Testing Strategy

- **Unit Tests**: Mock storage backends, test each implementation separately
- **Integration Tests**: Real backends (S3, GCS) with test credentials (marked for CI skip)
- **Acceptance Tests**: End-to-end scenarios (upload → retrieve → delete)
- **Property Tests**: Key validation, URL signing, metadata preservation
- **Performance Tests**: Large file uploads, concurrent operations

## Alternatives Considered

### 1. Use Third-Party Library (e.g., fsspec, cloudpathlib)

**Rejected**: These libraries are sync-first and don't integrate well with FastAPI's async patterns. Custom implementation gives us full control over async operations, error handling, and FastAPI integration.

### 2. Build Only S3 Backend

**Rejected**: Many users deploy on Railway or Render with persistent volumes (no S3). Supporting local filesystem from day one makes svc-infra accessible to all deployment scenarios.

### 3. Store Files in Database (PostgreSQL BYTEA)

**Rejected**: Database storage doesn't scale well for large files. BYTEA columns increase backup size, slow down queries, and don't support features like CDN delivery or image transformations.

### 4. Use APF Payments for File Storage

**Rejected**: APF Payments is for payment processing, not file storage. Mixing concerns would violate separation of concerns principle.

## Consequences

### Positive

1. **Reusability**: All applications built on svc-infra get file storage for free
2. **Flexibility**: Switch backends without code changes (local → S3 → GCS)
3. **Railway-Friendly**: Works perfectly with Railway persistent volumes
4. **Testing**: MemoryBackend makes unit tests fast and isolated
5. **Security**: Signed URLs and validation baked in from day one
6. **Observability**: Built-in metrics and logging for production monitoring

### Negative

1. **Maintenance Burden**: Need to maintain multiple backend implementations
2. **Dependency Management**: Each backend adds dependencies (boto3, google-cloud-storage, etc.)
3. **Testing Complexity**: Need credentials for integration tests
4. **Learning Curve**: Users need to understand backend configuration

### Neutral

1. **API Surface**: Adds new public APIs to svc-infra
2. **Documentation**: Requires comprehensive docs for each backend
3. **Migration**: Existing apps need to migrate from placeholder storage

## Implementation Plan

See `.github/PLAN.md` Section 22 for detailed implementation checklist.

**Priority**: MUST-HAVE for v1 (foundational infrastructure)

**Timeline Estimate**: ~15 days (3 weeks, 1 developer)

**Dependencies**: None (can be built in parallel)

## References

- [AWS S3 API](https://docs.aws.amazon.com/s3/)
- [DigitalOcean Spaces](https://docs.digitalocean.com/products/spaces/)
- [Railway Volumes](https://docs.railway.app/reference/volumes)
- [Google Cloud Storage](https://cloud.google.com/storage/docs)
- [Cloudinary API](https://cloudinary.com/documentation)
- [PEP 544: Protocols](https://peps.python.org/pep-0544/)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)

## Revision History

- 2025-11-17: Initial draft (Research & Design phase)
