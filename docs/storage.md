# Storage System

`svc_infra.storage` provides a backend-agnostic file storage abstraction with support for multiple providers (local filesystem, S3-compatible services, Google Cloud Storage, Cloudinary, and in-memory storage). The system enables applications to store and retrieve files without coupling to a specific storage provider, making it easy to switch backends or support multiple environments.

## Overview

The storage system provides:

- **Backend abstraction**: Write code once, deploy to any storage provider
- **Multiple backends**: Local filesystem, S3-compatible (AWS S3, DigitalOcean Spaces, Wasabi, Backblaze B2, Minio), Google Cloud Storage (coming soon), Cloudinary (coming soon), in-memory (testing)
- **Signed URLs**: Secure, time-limited access to files without exposing raw paths
- **Metadata support**: Attach custom metadata (user_id, tenant_id, tags) to stored files
- **Key validation**: Automatic validation of storage keys to prevent path traversal and other attacks
- **FastAPI integration**: One-line setup with dependency injection
- **Health checks**: Built-in storage backend health monitoring
- **Auto-detection**: Automatically detect and configure backend from environment variables

## Architecture

All storage backends implement the `StorageBackend` protocol with these core operations:

- `put(key, data, content_type, metadata)` → Store file and return URL
- `get(key)` → Retrieve file content
- `delete(key)` → Remove file
- `exists(key)` → Check if file exists
- `get_url(key, expires_in, download)` → Generate signed/public URL
- `list_keys(prefix, limit)` → List stored files
- `get_metadata(key)` → Get file metadata

This abstraction enables:
- Switching storage providers without code changes
- Testing with in-memory backend
- Multi-region/multi-provider deployments
- Provider-specific features (S3 presigned URLs, Cloudinary transformations)

## Quick Start

### Installation

Storage dependencies are included in svc-infra. For S3 support, ensure `aioboto3` is installed:

```bash
poetry add svc-infra
```

### One-Line Integration

```python
from fastapi import FastAPI
from svc_infra.storage import add_storage

app = FastAPI()

# Auto-detect backend from environment
storage = add_storage(app)
```

### Using Storage in Routes

```python
from fastapi import APIRouter, Depends, UploadFile
from svc_infra.storage import get_storage, StorageBackend

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile,
    storage: StorageBackend = Depends(get_storage),
):
    """Upload a file and return its URL."""
    content = await file.read()

    url = await storage.put(
        key=f"uploads/{file.filename}",
        data=content,
        content_type=file.content_type or "application/octet-stream",
        metadata={"uploader": "user_123", "timestamp": "2025-11-18"}
    )

    return {"url": url, "filename": file.filename}

@router.get("/download/{filename}")
async def download_file(
    filename: str,
    storage: StorageBackend = Depends(get_storage),
):
    """Download a file by filename."""
    key = f"uploads/{filename}"

    try:
        content = await storage.get(key)
        return Response(content=content, media_type="application/octet-stream")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

@router.delete("/files/{filename}")
async def delete_file(
    filename: str,
    storage: StorageBackend = Depends(get_storage),
):
    """Delete a file."""
    key = f"uploads/{filename}"
    await storage.delete(key)
    return {"status": "deleted"}
```

## Configuration

### Environment Variables

#### Backend Selection

- `STORAGE_BACKEND`: Explicit backend type (`local`, `s3`, `gcs`, `cloudinary`, `memory`)
  - If not set, auto-detection is used (see Auto-Detection section)

#### Local Backend

For Railway persistent volumes, Render disks, or local development:

- `STORAGE_BASE_PATH`: Directory for files (default: `/data/uploads`)
- `STORAGE_BASE_URL`: URL for file serving (default: `http://localhost:8000/files`)
- `STORAGE_URL_SECRET`: Secret for signing URLs (auto-generated if not set)
- `STORAGE_URL_EXPIRATION`: Default URL expiration in seconds (default: `3600`)

#### S3 Backend

For AWS S3, DigitalOcean Spaces, Wasabi, Backblaze B2, Minio, or any S3-compatible service:

- `STORAGE_S3_BUCKET`: Bucket name (required)
- `STORAGE_S3_REGION`: AWS region (default: `us-east-1`)
- `STORAGE_S3_ENDPOINT`: Custom endpoint URL for S3-compatible services
- `STORAGE_S3_ACCESS_KEY`: Access key (falls back to `AWS_ACCESS_KEY_ID`)
- `STORAGE_S3_SECRET_KEY`: Secret key (falls back to `AWS_SECRET_ACCESS_KEY`)

#### GCS Backend (Coming Soon)

For Google Cloud Storage:

- `STORAGE_GCS_BUCKET`: Bucket name
- `STORAGE_GCS_PROJECT`: GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON

#### Cloudinary Backend (Coming Soon)

For image optimization and transformations:

- `CLOUDINARY_URL`: Cloudinary connection URL
- `STORAGE_CLOUDINARY_CLOUD_NAME`: Cloud name
- `STORAGE_CLOUDINARY_API_KEY`: API key
- `STORAGE_CLOUDINARY_API_SECRET`: API secret

### Auto-Detection

When `STORAGE_BACKEND` is not set, the system auto-detects the backend in this order:

1. **Railway Volume**: If `RAILWAY_VOLUME_MOUNT_PATH` exists → `LocalBackend`
2. **S3 Credentials**: If `AWS_ACCESS_KEY_ID` or `STORAGE_S3_BUCKET` exists → `S3Backend`
3. **GCS Credentials**: If `GOOGLE_APPLICATION_CREDENTIALS` exists → `GCSBackend` (coming soon)
4. **Cloudinary**: If `CLOUDINARY_URL` exists → `CloudinaryBackend` (coming soon)
5. **Default**: `MemoryBackend` (with warning about data loss)

**Production Recommendation**: Always set `STORAGE_BACKEND` explicitly to avoid unexpected behavior.

## Backend Comparison

### When to Use Each Backend

| Backend | Best For | Pros | Cons |
|---------|----------|------|------|
| **LocalBackend** | Railway, Render, small deployments, development | Simple, no external dependencies, fast | Not scalable across multiple servers, requires persistent volumes |
| **S3Backend** | Production deployments, multi-region, CDN integration | Highly scalable, durable, integrates with CloudFront/CDN | Requires AWS account or S3-compatible service, potential egress costs |
| **GCSBackend** | GCP-native deployments | GCP integration, global CDN | Requires GCP account |
| **CloudinaryBackend** | Image-heavy applications | Automatic image optimization, transformations, CDN | Additional service cost, image-focused |
| **MemoryBackend** | Testing, CI/CD | Fast, no setup | Data lost on restart, limited by RAM |

### Provider-Specific Notes

#### Railway Persistent Volumes

```bash
# Railway automatically sets this variable
RAILWAY_VOLUME_MOUNT_PATH=/data

# Storage auto-detects and uses LocalBackend
STORAGE_BASE_PATH=/data/uploads
```

#### AWS S3

```bash
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=my-app-uploads
STORAGE_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

#### DigitalOcean Spaces

```bash
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=my-app-uploads
STORAGE_S3_REGION=nyc3
STORAGE_S3_ENDPOINT=https://nyc3.digitaloceanspaces.com
STORAGE_S3_ACCESS_KEY=...
STORAGE_S3_SECRET_KEY=...
```

#### Wasabi

```bash
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=my-app-uploads
STORAGE_S3_REGION=us-east-1
STORAGE_S3_ENDPOINT=https://s3.wasabisys.com
STORAGE_S3_ACCESS_KEY=...
STORAGE_S3_SECRET_KEY=...
```

#### Backblaze B2

```bash
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=my-app-uploads
STORAGE_S3_REGION=us-west-000
STORAGE_S3_ENDPOINT=https://s3.us-west-000.backblazeb2.com
STORAGE_S3_ACCESS_KEY=...
STORAGE_S3_SECRET_KEY=...
```

#### Minio (Self-Hosted)

```bash
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=my-app-uploads
STORAGE_S3_REGION=us-east-1
STORAGE_S3_ENDPOINT=https://minio.example.com
STORAGE_S3_ACCESS_KEY=minioadmin
STORAGE_S3_SECRET_KEY=minioadmin
```

## Examples

### Profile Picture Upload

```python
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from svc_infra.storage import get_storage, StorageBackend
from PIL import Image
import io

router = APIRouter()

MAX_SIZE = 2 * 1024 * 1024  # 2MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

@router.post("/users/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    storage: StorageBackend = Depends(get_storage),
    current_user=Depends(get_current_user),  # Your auth dependency
):
    """Upload user profile picture."""
    # Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed: {ALLOWED_TYPES}"
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {MAX_SIZE} bytes"
        )

    # Validate image and resize
    try:
        image = Image.open(io.BytesIO(content))
        image.verify()  # Verify it's a valid image

        # Reopen and resize
        image = Image.open(io.BytesIO(content))
        image.thumbnail((200, 200))

        # Save to bytes
        output = io.BytesIO()
        image.save(output, format=image.format)
        resized_content = output.getvalue()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Store with user-specific key
    key = f"avatars/{current_user.id}/profile.{file.filename.split('.')[-1]}"

    url = await storage.put(
        key=key,
        data=resized_content,
        content_type=file.content_type,
        metadata={
            "user_id": str(current_user.id),
            "original_filename": file.filename,
            "uploaded_at": datetime.utcnow().isoformat(),
        }
    )

    # Update user record with new avatar URL
    # await update_user_avatar(current_user.id, url)

    return {"avatar_url": url}
```

### Document Storage with Metadata

```python
from fastapi import APIRouter, Depends, UploadFile, Query
from svc_infra.storage import get_storage, StorageBackend
from typing import List, Optional

router = APIRouter()

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    tags: List[str] = Query(default=[]),
    category: str = Query(default="general"),
    storage: StorageBackend = Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """Upload a document with metadata."""
    content = await file.read()

    # Generate unique key
    file_id = uuid4()
    key = f"documents/{current_user.id}/{category}/{file_id}/{file.filename}"

    url = await storage.put(
        key=key,
        data=content,
        content_type=file.content_type or "application/octet-stream",
        metadata={
            "user_id": str(current_user.id),
            "document_id": str(file_id),
            "category": category,
            "tags": ",".join(tags),
            "original_filename": file.filename,
            "size": len(content),
            "uploaded_at": datetime.utcnow().isoformat(),
        }
    )

    # Store document record in database
    # document = await create_document_record(...)

    return {
        "document_id": str(file_id),
        "url": url,
        "filename": file.filename,
        "size": len(content),
        "category": category,
        "tags": tags,
    }

@router.get("/documents")
async def list_documents(
    category: Optional[str] = None,
    storage: StorageBackend = Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """List user's documents."""
    prefix = f"documents/{current_user.id}/"
    if category:
        prefix += f"{category}/"

    keys = await storage.list_keys(prefix=prefix, limit=100)

    # Get metadata for each file
    documents = []
    for key in keys:
        metadata = await storage.get_metadata(key)
        documents.append({
            "key": key,
            "filename": metadata.get("original_filename"),
            "size": metadata.get("size"),
            "category": metadata.get("category"),
            "uploaded_at": metadata.get("uploaded_at"),
        })

    return {"documents": documents}
```

### Tenant-Scoped File Storage

```python
from fastapi import APIRouter, Depends, UploadFile
from svc_infra.storage import get_storage, StorageBackend
from svc_infra.tenancy import require_tenant_id

router = APIRouter()

@router.post("/tenant-files/upload")
async def upload_tenant_file(
    file: UploadFile,
    storage: StorageBackend = Depends(get_storage),
    tenant_id: str = Depends(require_tenant_id),
    current_user=Depends(get_current_user),
):
    """Upload a file scoped to current tenant."""
    content = await file.read()

    # Tenant-scoped key ensures isolation
    key = f"tenants/{tenant_id}/files/{uuid4()}/{file.filename}"

    url = await storage.put(
        key=key,
        data=content,
        content_type=file.content_type or "application/octet-stream",
        metadata={
            "tenant_id": tenant_id,
            "user_id": str(current_user.id),
            "filename": file.filename,
            "uploaded_at": datetime.utcnow().isoformat(),
        }
    )

    return {"url": url, "filename": file.filename}

@router.get("/tenant-files")
async def list_tenant_files(
    storage: StorageBackend = Depends(get_storage),
    tenant_id: str = Depends(require_tenant_id),
):
    """List files for current tenant only."""
    # Prefix ensures tenant isolation
    prefix = f"tenants/{tenant_id}/files/"

    keys = await storage.list_keys(prefix=prefix, limit=100)

    return {"files": keys, "count": len(keys)}
```

### Signed URL Generation

```python
from fastapi import APIRouter, Depends, HTTPException
from svc_infra.storage import get_storage, StorageBackend

router = APIRouter()

@router.get("/files/{file_id}/download-url")
async def get_download_url(
    file_id: str,
    expires_in: int = Query(default=3600, ge=60, le=86400),  # 1 min to 24 hours
    download: bool = Query(default=True),
    storage: StorageBackend = Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """Generate a signed URL for file download."""
    # Verify user owns the file
    # file = await get_file_record(file_id)
    # if file.user_id != current_user.id:
    #     raise HTTPException(status_code=403, detail="Access denied")

    key = f"uploads/{file_id}/document.pdf"

    # Check file exists
    if not await storage.exists(key):
        raise HTTPException(status_code=404, detail="File not found")

    # Generate signed URL
    url = await storage.get_url(
        key=key,
        expires_in=expires_in,
        download=download  # If True, browser downloads instead of displaying
    )

    return {
        "url": url,
        "expires_in": expires_in,
        "expires_at": (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
    }
```

### Large File Uploads with Progress

```python
from fastapi import APIRouter, Depends, UploadFile, BackgroundTasks
from svc_infra.storage import get_storage, StorageBackend

router = APIRouter()

@router.post("/large-files/upload")
async def upload_large_file(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    storage: StorageBackend = Depends(get_storage),
    current_user=Depends(get_current_user),
):
    """Upload large file with background processing."""
    # For very large files, consider chunked uploads
    # This is a simple example that reads entire file

    file_id = uuid4()
    key = f"large-files/{current_user.id}/{file_id}/{file.filename}"

    # Read file in chunks
    chunks = []
    while chunk := await file.read(1024 * 1024):  # 1MB chunks
        chunks.append(chunk)

    content = b"".join(chunks)

    # Store file
    url = await storage.put(
        key=key,
        data=content,
        content_type=file.content_type or "application/octet-stream",
        metadata={
            "user_id": str(current_user.id),
            "file_id": str(file_id),
            "size": len(content),
            "uploaded_at": datetime.utcnow().isoformat(),
        }
    )

    # Background task for post-processing (virus scan, thumbnail generation, etc.)
    # background_tasks.add_task(process_file, file_id, key)

    return {
        "file_id": str(file_id),
        "url": url,
        "size": len(content),
        "status": "uploaded"
    }
```

## Production Recommendations

### Railway Deployments

Railway persistent volumes are ideal for simple deployments:

```bash
# Railway automatically mounts volume
RAILWAY_VOLUME_MOUNT_PATH=/data

# Storage auto-detects LocalBackend
# No additional configuration needed
```

**Pros**:
- Simple setup, no external services
- Cost-effective for small/medium apps
- Fast local access

**Cons**:
- Single server only (not suitable for horizontal scaling)
- Manual backups required
- Volume size limits

### AWS Deployments

S3 is recommended for production:

```bash
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=myapp-uploads-prod
STORAGE_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

**Additional recommendations**:
- Enable versioning for backup/recovery
- Configure lifecycle policies to archive old files to Glacier
- Use CloudFront CDN for global distribution
- Enable server-side encryption (SSE-S3 or SSE-KMS)
- Set up bucket policies for least-privilege access

### DigitalOcean Deployments

DigitalOcean Spaces (S3-compatible) offers simple pricing:

```bash
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=myapp-uploads
STORAGE_S3_REGION=nyc3
STORAGE_S3_ENDPOINT=https://nyc3.digitaloceanspaces.com
STORAGE_S3_ACCESS_KEY=...
STORAGE_S3_SECRET_KEY=...
```

**Pros**:
- Predictable pricing ($5/250GB)
- Built-in CDN
- S3-compatible API

### GCP Deployments

Google Cloud Storage for GCP-native apps:

```bash
STORAGE_BACKEND=gcs
STORAGE_GCS_BUCKET=myapp-uploads
STORAGE_GCS_PROJECT=my-gcp-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

(Coming soon)

### Image-Heavy Applications

Consider Cloudinary for automatic optimization:

```bash
STORAGE_BACKEND=cloudinary
CLOUDINARY_URL=cloudinary://...
```

**Features**:
- Automatic image optimization
- On-the-fly transformations (resize, crop, format)
- Global CDN
- Video support

(Coming soon)

## Security Considerations

### Never Expose Raw File Paths

❌ **Bad**:
```python
# Don't return raw storage keys or file paths
return {"path": "/data/uploads/secret-document.pdf"}
```

✅ **Good**:
```python
# Return signed URLs with expiration
url = await storage.get_url(key, expires_in=3600)
return {"url": url}
```

### Always Use Signed URLs with Expiration

```python
# Short expiration for sensitive documents
url = await storage.get_url(key, expires_in=300)  # 5 minutes

# Longer expiration for public assets
url = await storage.get_url(key, expires_in=86400)  # 24 hours
```

### Validate File Types and Sizes Before Upload

```python
MAX_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf"}

if file.content_type not in ALLOWED_TYPES:
    raise HTTPException(status_code=415, detail="Unsupported file type")

content = await file.read()
if len(content) > MAX_SIZE:
    raise HTTPException(status_code=413, detail="File too large")
```

### Scan for Viruses

Integration with ClamAV or similar (coming in future version):

```python
# Future API
from svc_infra.storage.scanners import scan_file

result = await scan_file(content)
if result.is_infected:
    raise HTTPException(status_code=400, detail="File contains malware")
```

### Implement Tenant Isolation via Key Prefixes

```python
# Always scope keys by tenant
key = f"tenants/{tenant_id}/documents/{file_id}"

# Verify access before operations
if not await verify_tenant_access(current_user, tenant_id):
    raise HTTPException(status_code=403, detail="Access denied")
```

### Use IAM Policies for Least-Privilege Access

For S3/GCS, create service accounts with minimal permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::myapp-uploads-prod",
        "arn:aws:s3:::myapp-uploads-prod/*"
      ]
    }
  ]
}
```

### Enable Encryption at Rest

For S3:
```bash
# Enable default encryption in bucket settings
aws s3api put-bucket-encryption \
  --bucket myapp-uploads-prod \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

## Troubleshooting

### Error: "Storage not configured"

**Cause**: `add_storage()` was not called or `get_storage()` dependency used without configuration.

**Solution**:
```python
from svc_infra.storage import add_storage

app = FastAPI()
storage = add_storage(app)  # Add this line
```

### Error: "No module named 'aioboto3'"

**Cause**: S3Backend requires `aioboto3` dependency.

**Solution**:
```bash
poetry add aioboto3
```

### Error: "Access Denied" (S3)

**Cause**: Invalid credentials or insufficient IAM permissions.

**Solution**:
- Verify `STORAGE_S3_ACCESS_KEY` and `STORAGE_S3_SECRET_KEY`
- Check IAM policy allows required S3 actions
- Verify bucket name and region are correct

### Error: "Bucket does not exist"

**Cause**: S3 bucket not created or wrong bucket name.

**Solution**:
```bash
# Create bucket
aws s3 mb s3://myapp-uploads-prod --region us-east-1

# Or via S3 console
```

### Files Not Persisting (LocalBackend)

**Cause**: Using in-memory filesystem or container without persistent volume.

**Solution**:
- Railway: Ensure persistent volume is mounted
- Docker: Mount volume: `docker run -v /data/uploads:/data/uploads ...`
- Render: Use persistent disks feature

### URLs Expire Too Quickly

**Cause**: Default expiration is 1 hour.

**Solution**:
```python
# Increase expiration
url = await storage.get_url(key, expires_in=86400)  # 24 hours

# Or set default in environment
STORAGE_URL_EXPIRATION=86400
```

### Large File Uploads Fail

**Cause**: Request timeout or size limits.

**Solution**:
```python
# Increase timeouts in uvicorn
uvicorn main:app --timeout-keep-alive 300

# Or chunk uploads for very large files (>100MB)
```

## API Reference

### Core Functions

#### `add_storage(app, backend, serve_files, file_route_prefix)`

Integrate storage backend with FastAPI application.

**Parameters**:
- `app: FastAPI` - Application instance
- `backend: Optional[StorageBackend]` - Storage backend (auto-detected if None)
- `serve_files: bool` - Mount file serving route (LocalBackend only, default: False)
- `file_route_prefix: str` - URL prefix for files (default: "/files")

**Returns**: `StorageBackend` instance

**Example**:
```python
storage = add_storage(app)
```

#### `easy_storage(backend, **kwargs)`

Create storage backend with auto-detection.

**Parameters**:
- `backend: Optional[str]` - Backend type ("local", "s3", "memory") or None for auto-detect
- `**kwargs` - Backend-specific configuration

**Returns**: `StorageBackend` instance

**Example**:
```python
storage = easy_storage(backend="s3", bucket="uploads", region="us-east-1")
```

#### `get_storage(request)`

FastAPI dependency to inject storage backend.

**Parameters**:
- `request: Request` - FastAPI request

**Returns**: `StorageBackend` from app.state.storage

**Example**:
```python
async def upload(storage: StorageBackend = Depends(get_storage)):
    ...
```

### StorageBackend Protocol

All backends implement these methods:

#### `async put(key, data, content_type, metadata=None)`

Store file and return URL.

**Parameters**:
- `key: str` - Storage key (path)
- `data: bytes` - File content
- `content_type: str` - MIME type
- `metadata: Optional[dict]` - Custom metadata

**Returns**: `str` - File URL

**Raises**: `InvalidKeyError`, `PermissionDeniedError`, `QuotaExceededError`, `StorageError`

#### `async get(key)`

Retrieve file content.

**Parameters**:
- `key: str` - Storage key

**Returns**: `bytes` - File content

**Raises**: `FileNotFoundError`, `PermissionDeniedError`, `StorageError`

#### `async delete(key)`

Remove file.

**Parameters**:
- `key: str` - Storage key

**Returns**: `bool` - True if deleted, False if not found

**Raises**: `PermissionDeniedError`, `StorageError`

#### `async exists(key)`

Check if file exists.

**Parameters**:
- `key: str` - Storage key

**Returns**: `bool` - True if exists

#### `async get_url(key, expires_in=3600, download=False)`

Generate signed URL.

**Parameters**:
- `key: str` - Storage key
- `expires_in: int` - Expiration in seconds (default: 3600)
- `download: bool` - Force download vs display (default: False)

**Returns**: `str` - Signed URL

**Raises**: `FileNotFoundError`, `StorageError`

#### `async list_keys(prefix="", limit=1000)`

List stored files.

**Parameters**:
- `prefix: str` - Key prefix filter (default: "")
- `limit: int` - Max results (default: 1000)

**Returns**: `List[str]` - List of keys

#### `async get_metadata(key)`

Get file metadata.

**Parameters**:
- `key: str` - Storage key

**Returns**: `dict` - Metadata dictionary

**Raises**: `FileNotFoundError`, `StorageError`

### Exceptions

All exceptions inherit from `StorageError`:

- `StorageError` - Base exception
- `FileNotFoundError` - File doesn't exist
- `PermissionDeniedError` - Access denied
- `QuotaExceededError` - Storage quota exceeded
- `InvalidKeyError` - Invalid key format

## Health Checks

Storage backend health is automatically registered when using `add_storage()`:

```python
# Health check endpoint
GET /_ops/health

# Response
{
  "status": "healthy",
  "storage": {
    "backend": "S3Backend",
    "status": "connected"
  }
}
```

## See Also

- [ADR-0012: Generic File Storage System](/src/svc_infra/docs/adr/0012-storage-system.md) - Design decisions
- [API Integration Guide](/src/svc_infra/docs/api.md) - FastAPI integration patterns
- [Tenancy Guide](/src/svc_infra/docs/tenancy.md) - Multi-tenant file isolation
- [Security Guide](/src/svc_infra/docs/security.md) - Security best practices
