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

---

## CDN Integration

### CloudFront with S3

Amazon CloudFront provides global edge caching for your S3 files:

#### 1. Create CloudFront Distribution

```bash
aws cloudfront create-distribution \
  --origin-domain-name myapp-uploads.s3.amazonaws.com \
  --default-root-object index.html
```

#### 2. Configure Signed URLs

```python
import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
import base64

def sign_cloudfront_url(
    url: str,
    key_pair_id: str,
    private_key_path: str,
    expires_at: datetime.datetime,
) -> str:
    """Generate CloudFront signed URL."""
    policy = {
        "Statement": [{
            "Resource": url,
            "Condition": {
                "DateLessThan": {
                    "AWS:EpochTime": int(expires_at.timestamp())
                }
            }
        }]
    }

    policy_json = json.dumps(policy, separators=(",", ":"))
    policy_b64 = base64.b64encode(policy_json.encode()).decode()
    # URL-safe base64
    policy_b64 = policy_b64.replace("+", "-").replace("=", "_").replace("/", "~")

    with open(private_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    signature = private_key.sign(
        policy_json.encode(),
        padding.PKCS1v15(),
        hashes.SHA1()
    )
    signature_b64 = base64.b64encode(signature).decode()
    signature_b64 = signature_b64.replace("+", "-").replace("=", "_").replace("/", "~")

    return f"{url}?Policy={policy_b64}&Signature={signature_b64}&Key-Pair-Id={key_pair_id}"
```

#### 3. Integration with Storage Backend

```python
from svc_infra.storage import StorageBackend
from fastapi import Depends

class CDNStorageWrapper:
    """Wrapper that returns CDN URLs instead of S3 presigned URLs."""

    def __init__(
        self,
        backend: StorageBackend,
        cdn_domain: str,
        key_pair_id: str,
        private_key_path: str,
    ):
        self.backend = backend
        self.cdn_domain = cdn_domain
        self.key_pair_id = key_pair_id
        self.private_key_path = private_key_path

    async def put(self, key: str, data: bytes, content_type: str, metadata=None) -> str:
        # Store in S3
        await self.backend.put(key, data, content_type, metadata)
        # Return CDN URL
        return f"https://{self.cdn_domain}/{key}"

    async def get_url(self, key: str, expires_in: int = 3600, download: bool = False) -> str:
        url = f"https://{self.cdn_domain}/{key}"
        if download:
            url += "?response-content-disposition=attachment"

        expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
        return sign_cloudfront_url(
            url, self.key_pair_id, self.private_key_path, expires_at
        )

    # Delegate other methods
    async def get(self, key: str) -> bytes:
        return await self.backend.get(key)

    async def delete(self, key: str) -> bool:
        return await self.backend.delete(key)

    async def exists(self, key: str) -> bool:
        return await self.backend.exists(key)
```

### Cloudflare R2 with Workers

Cloudflare R2 is S3-compatible with zero egress fees:

```bash
# Environment configuration
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=myapp-uploads
STORAGE_S3_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
STORAGE_S3_ACCESS_KEY=...
STORAGE_S3_SECRET_KEY=...
```

#### Custom Domain with Cloudflare

```python
# R2 URLs can be served via custom domain
CDN_DOMAIN = "cdn.example.com"

async def get_cdn_url(storage: StorageBackend, key: str) -> str:
    # For public files
    return f"https://{CDN_DOMAIN}/{key}"

    # For private files, use R2 presigned URL
    return await storage.get_url(key, expires_in=3600)
```

### DigitalOcean Spaces CDN

Spaces includes built-in CDN:

```bash
# Enable CDN in Spaces settings, then use CDN endpoint
# Original: https://nyc3.digitaloceanspaces.com/mybucket/file.jpg
# CDN: https://mybucket.nyc3.cdn.digitaloceanspaces.com/file.jpg

CDN_ENDPOINT=mybucket.nyc3.cdn.digitaloceanspaces.com
```

```python
async def get_spaces_cdn_url(key: str) -> str:
    return f"https://{os.environ['CDN_ENDPOINT']}/{key}"
```

### BunnyCDN (Any Origin)

BunnyCDN works with any storage backend:

```python
import hashlib
import time

def sign_bunny_url(
    url: str,
    security_key: str,
    expires_in: int = 3600,
) -> str:
    """Generate BunnyCDN signed URL."""
    expires = int(time.time()) + expires_in

    # Extract path from URL
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path

    # Generate token
    token_base = f"{security_key}{path}{expires}"
    token = hashlib.md5(token_base.encode()).digest()
    token_b64 = base64.b64encode(token).decode()
    token_b64 = token_b64.replace("\n", "").replace("+", "-").replace("/", "_").replace("=", "")

    return f"{url}?token={token_b64}&expires={expires}"

# Usage
CDN_URL = "https://myzone.b-cdn.net"
SECURITY_KEY = os.environ["BUNNY_SECURITY_KEY"]

async def get_bunny_url(key: str, expires_in: int = 3600) -> str:
    url = f"{CDN_URL}/{key}"
    return sign_bunny_url(url, SECURITY_KEY, expires_in)
```

### Cache Invalidation

When files are updated, invalidate CDN cache:

```python
import httpx

class CDNInvalidator:
    """Invalidate CDN cache when files change."""

    async def invalidate_cloudfront(self, distribution_id: str, paths: list[str]):
        """Invalidate CloudFront cache."""
        import boto3
        client = boto3.client("cloudfront")
        client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": len(paths), "Items": paths},
                "CallerReference": str(time.time()),
            }
        )

    async def invalidate_bunny(self, url: str, api_key: str):
        """Invalidate BunnyCDN cache."""
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.bunny.net/purge",
                params={"url": url},
                headers={"AccessKey": api_key},
            )

    async def invalidate_cloudflare(self, zone_id: str, api_token: str, urls: list[str]):
        """Invalidate Cloudflare cache."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache",
                json={"files": urls},
                headers={"Authorization": f"Bearer {api_token}"},
            )

# Integrate with storage operations
async def put_with_invalidation(
    storage: StorageBackend,
    invalidator: CDNInvalidator,
    key: str,
    data: bytes,
    content_type: str,
) -> str:
    # Upload new version
    url = await storage.put(key, data, content_type)

    # Invalidate old cache
    await invalidator.invalidate_cloudfront(
        DISTRIBUTION_ID,
        [f"/{key}"]
    )

    return url
```

---

## Cost Optimization

### Storage Backend Cost Comparison

| Provider | Storage (GB/mo) | Egress (GB) | Requests (10K) | Best For |
|----------|-----------------|-------------|----------------|----------|
| **AWS S3 Standard** | $0.023 | $0.09 | $0.005 GET | General purpose |
| **AWS S3 IA** | $0.0125 | $0.09 | $0.01 GET | Infrequent access |
| **AWS S3 Glacier** | $0.004 | $0.09 | $0.05 GET | Archives |
| **Cloudflare R2** | $0.015 | **$0.00** | $0.36/million | High egress |
| **Backblaze B2** | $0.006 | $0.01 | Free | Budget-friendly |
| **DigitalOcean Spaces** | $5/250GB | Included | Included | Simplicity |
| **Wasabi** | $0.0059 | **$0.00** | Free | Cold storage |

### Choosing the Right Backend

```python
def recommend_storage_backend(
    monthly_storage_gb: float,
    monthly_egress_gb: float,
    access_pattern: str,  # "hot", "warm", "cold"
) -> str:
    """Recommend optimal storage backend based on usage."""

    # Calculate costs
    costs = {}

    # AWS S3 Standard
    costs["s3_standard"] = (monthly_storage_gb * 0.023) + (monthly_egress_gb * 0.09)

    # Cloudflare R2 (no egress)
    costs["r2"] = monthly_storage_gb * 0.015

    # Backblaze B2
    costs["b2"] = (monthly_storage_gb * 0.006) + (monthly_egress_gb * 0.01)

    # Wasabi (no egress but 90-day minimum)
    costs["wasabi"] = monthly_storage_gb * 0.0059

    # Add access pattern considerations
    if access_pattern == "hot" and monthly_egress_gb > 100:
        # High egress → R2 wins
        return "Cloudflare R2"
    elif access_pattern == "cold":
        # Archive → Wasabi or Glacier
        return "Wasabi or S3 Glacier"
    elif monthly_storage_gb < 50 and monthly_egress_gb < 100:
        # Small scale → DigitalOcean Spaces for simplicity
        return "DigitalOcean Spaces"
    else:
        # General → pick cheapest
        return min(costs, key=costs.get)
```

### S3 Storage Classes

Use lifecycle policies to automatically transition files:

```python
import boto3

def setup_lifecycle_policy(bucket: str):
    """Configure S3 lifecycle for cost optimization."""
    s3 = boto3.client("s3")

    s3.put_bucket_lifecycle_configuration(
        Bucket=bucket,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "TransitionToIA",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "documents/"},
                    "Transitions": [
                        {
                            "Days": 30,
                            "StorageClass": "STANDARD_IA"
                        }
                    ]
                },
                {
                    "ID": "TransitionToGlacier",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "archives/"},
                    "Transitions": [
                        {
                            "Days": 90,
                            "StorageClass": "GLACIER_IR"
                        }
                    ]
                },
                {
                    "ID": "ExpireOldVersions",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "NoncurrentVersionExpiration": {
                        "NoncurrentDays": 30
                    }
                },
                {
                    "ID": "CleanupMultipartUploads",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "AbortIncompleteMultipartUpload": {
                        "DaysAfterInitiation": 7
                    }
                }
            ]
        }
    )
```

### Intelligent Tiering

Let AWS automatically move files between tiers:

```python
async def put_with_intelligent_tiering(
    storage: S3Backend,
    key: str,
    data: bytes,
    content_type: str,
) -> str:
    """Store with Intelligent-Tiering for automatic cost optimization."""
    await storage._client.put_object(
        Bucket=storage.bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        StorageClass="INTELLIGENT_TIERING",
    )
    return await storage.get_url(key)
```

### Compression

Compress before storing to reduce costs:

```python
import gzip
import zlib

async def put_compressed(
    storage: StorageBackend,
    key: str,
    data: bytes,
    content_type: str,
) -> tuple[str, int]:
    """Store compressed data, return URL and savings percentage."""
    original_size = len(data)

    # Skip compression for already-compressed formats
    skip_compression = {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "video/mp4", "video/webm",
        "application/zip", "application/gzip",
    }

    if content_type in skip_compression:
        url = await storage.put(key, data, content_type)
        return url, 0

    # Compress with gzip
    compressed = gzip.compress(data, compresslevel=6)

    # Only use compressed if it's actually smaller
    if len(compressed) < original_size * 0.9:  # At least 10% savings
        url = await storage.put(
            key + ".gz",
            compressed,
            content_type,
            metadata={"original-content-type": content_type, "compressed": "gzip"},
        )
        savings = int((1 - len(compressed) / original_size) * 100)
        return url, savings
    else:
        url = await storage.put(key, data, content_type)
        return url, 0

# Decompress on retrieval
async def get_decompressed(storage: StorageBackend, key: str) -> bytes:
    """Retrieve and decompress if needed."""
    data = await storage.get(key)

    if key.endswith(".gz"):
        return gzip.decompress(data)
    return data
```

### Deduplication

Avoid storing duplicate files:

```python
import hashlib

async def put_deduplicated(
    storage: StorageBackend,
    key: str,
    data: bytes,
    content_type: str,
    session,  # Database session
) -> str:
    """Store file with deduplication based on content hash."""
    # Calculate content hash
    content_hash = hashlib.sha256(data).hexdigest()

    # Check if we already have this content
    existing = await session.execute(
        select(FileRecord).where(FileRecord.content_hash == content_hash)
    )
    existing_file = existing.scalars().first()

    if existing_file:
        # Create reference to existing file
        await session.execute(
            insert(FileRecord).values(
                key=key,
                content_hash=content_hash,
                storage_key=existing_file.storage_key,  # Point to same storage
                size=len(data),
            )
        )
        return await storage.get_url(existing_file.storage_key)

    # Store new file
    storage_key = f"content/{content_hash[:2]}/{content_hash}"
    url = await storage.put(storage_key, data, content_type)

    await session.execute(
        insert(FileRecord).values(
            key=key,
            content_hash=content_hash,
            storage_key=storage_key,
            size=len(data),
        )
    )

    return url

# Delete with reference counting
async def delete_deduplicated(storage: StorageBackend, key: str, session) -> bool:
    """Delete file reference, only delete storage if no more references."""
    file_record = await session.get(FileRecord, key)
    if not file_record:
        return False

    # Count other references
    count = await session.execute(
        select(func.count()).where(
            FileRecord.storage_key == file_record.storage_key,
            FileRecord.key != key,
        )
    )
    other_refs = count.scalar()

    # Delete record
    await session.delete(file_record)

    # Delete from storage only if no other references
    if other_refs == 0:
        await storage.delete(file_record.storage_key)

    return True
```

### Monitoring Storage Costs

```python
from prometheus_client import Gauge, Counter

storage_bytes = Gauge(
    "storage_bytes_total",
    "Total bytes stored",
    ["backend", "tenant_id"],
)

storage_egress_bytes = Counter(
    "storage_egress_bytes_total",
    "Total bytes transferred out",
    ["backend"],
)

async def put_with_metrics(
    storage: StorageBackend,
    tenant_id: str,
    key: str,
    data: bytes,
    content_type: str,
) -> str:
    url = await storage.put(key, data, content_type)
    storage_bytes.labels(
        backend=type(storage).__name__,
        tenant_id=tenant_id,
    ).inc(len(data))
    return url

async def get_with_metrics(storage: StorageBackend, key: str) -> bytes:
    data = await storage.get(key)
    storage_egress_bytes.labels(
        backend=type(storage).__name__,
    ).inc(len(data))
    return data
```

### Cost Alerts

```python
# Prometheus alerting rule
ALERT StorageCostHigh
  expr: increase(storage_egress_bytes_total[24h]) > 100 * 1024 * 1024 * 1024  # 100GB/day
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "High storage egress detected"
    description: "Egress {{ $value | humanize1024 }} in last 24h"
```

---

## Provider-Specific Optimizations

### AWS S3

#### Transfer Acceleration

For global uploads, enable S3 Transfer Acceleration:

```bash
aws s3api put-bucket-accelerate-configuration \
  --bucket myapp-uploads \
  --accelerate-configuration Status=Enabled
```

```python
# Use accelerated endpoint
STORAGE_S3_ENDPOINT=https://myapp-uploads.s3-accelerate.amazonaws.com
```

#### Multipart Uploads for Large Files

```python
async def upload_large_file(
    storage: S3Backend,
    key: str,
    file_path: str,
    chunk_size: int = 100 * 1024 * 1024,  # 100MB chunks
) -> str:
    """Upload large file using multipart upload."""
    import aioboto3

    session = aioboto3.Session()
    async with session.client("s3") as s3:
        # Initiate multipart upload
        response = await s3.create_multipart_upload(
            Bucket=storage.bucket,
            Key=key,
        )
        upload_id = response["UploadId"]

        parts = []
        part_number = 1

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                # Upload part
                part = await s3.upload_part(
                    Bucket=storage.bucket,
                    Key=key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk,
                )
                parts.append({
                    "PartNumber": part_number,
                    "ETag": part["ETag"],
                })
                part_number += 1

        # Complete multipart upload
        await s3.complete_multipart_upload(
            Bucket=storage.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    return await storage.get_url(key)
```

### Cloudflare R2

#### Workers Integration

```javascript
// Cloudflare Worker for image resizing
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const key = url.pathname.slice(1);

    // Check for resize parameters
    const width = url.searchParams.get("w");
    const height = url.searchParams.get("h");

    const object = await env.BUCKET.get(key);
    if (!object) {
      return new Response("Not found", { status: 404 });
    }

    if (width || height) {
      // Use Cloudflare Image Resizing
      return fetch(request, {
        cf: {
          image: {
            width: parseInt(width) || undefined,
            height: parseInt(height) || undefined,
            fit: "contain",
          },
        },
      });
    }

    return new Response(object.body, {
      headers: {
        "content-type": object.httpMetadata.contentType,
        "cache-control": "public, max-age=31536000",
      },
    });
  },
};
```

### Backblaze B2

#### Native API for Lower Costs

```python
from b2sdk.v2 import InMemoryAccountInfo, B2Api

def get_b2_api() -> B2Api:
    """Get Backblaze B2 native API (lower cost than S3 compatibility)."""
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account(
        "production",
        os.environ["B2_APPLICATION_KEY_ID"],
        os.environ["B2_APPLICATION_KEY"],
    )
    return b2_api

async def upload_to_b2_native(
    key: str,
    data: bytes,
    content_type: str,
) -> str:
    """Upload using native B2 API (no S3 compatibility overhead)."""
    b2_api = get_b2_api()
    bucket = b2_api.get_bucket_by_name(os.environ["B2_BUCKET_NAME"])

    file_info = bucket.upload_bytes(
        data,
        key,
        content_type=content_type,
    )

    return f"https://f002.backblazeb2.com/file/{bucket.name}/{key}"
```

---

## See Also

- [API Integration Guide](./api.md) - FastAPI integration patterns
- [Tenancy Guide](./tenancy.md) - Multi-tenant file isolation
- [Security Guide](./security.md) - Security best practices
