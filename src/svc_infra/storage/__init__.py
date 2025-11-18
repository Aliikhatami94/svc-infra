"""
Generic file storage system for svc-infra.

Provides backend-agnostic file storage with support for multiple providers:
- Local filesystem (Railway volumes, Render, development)
- S3-compatible (AWS S3, DigitalOcean Spaces, Wasabi, Backblaze B2, Minio)
- Google Cloud Storage (coming soon)
- Cloudinary (coming soon)
- In-memory (testing)

Quick Start:
    >>> from svc_infra.storage import add_storage, easy_storage
    >>> from fastapi import FastAPI
    >>>
    >>> app = FastAPI()
    >>>
    >>> # Auto-detect backend from environment
    >>> storage = add_storage(app)
    >>>
    >>> # Or explicit backend
    >>> backend = easy_storage(backend="s3", bucket="my-uploads")
    >>> storage = add_storage(app, backend)

Usage in Routes:
    >>> from svc_infra.storage import get_storage, StorageBackend
    >>> from fastapi import Depends, UploadFile
    >>>
    >>> @router.post("/upload")
    >>> async def upload_file(
    ...     file: UploadFile,
    ...     storage: StorageBackend = Depends(get_storage),
    ... ):
    ...     content = await file.read()
    ...     url = await storage.put(
    ...         key=f"uploads/{file.filename}",
    ...         data=content,
    ...         content_type=file.content_type or "application/octet-stream",
    ...         metadata={"user_id": "user_123"}
    ...     )
    ...     return {"url": url}

Environment Variables:
    STORAGE_BACKEND: Backend type (local, s3, gcs, cloudinary, memory)

    Local:
        STORAGE_BASE_PATH: Directory for files (default: /data/uploads)
        STORAGE_BASE_URL: URL for file serving (default: http://localhost:8000/files)

    S3:
        STORAGE_S3_BUCKET: Bucket name (required)
        STORAGE_S3_REGION: AWS region (default: us-east-1)
        STORAGE_S3_ENDPOINT: Custom endpoint for S3-compatible services
        STORAGE_S3_ACCESS_KEY: Access key (falls back to AWS_ACCESS_KEY_ID)
        STORAGE_S3_SECRET_KEY: Secret key (falls back to AWS_SECRET_ACCESS_KEY)

See Also:
    - ADR-0012: Generic File Storage System design
    - docs/storage.md: Comprehensive storage guide
"""

from .add import add_storage, get_storage, health_check_storage
from .backends import LocalBackend, MemoryBackend, S3Backend
from .base import (
    FileNotFoundError,
    InvalidKeyError,
    PermissionDeniedError,
    QuotaExceededError,
    StorageBackend,
    StorageError,
)
from .easy import easy_storage
from .settings import StorageSettings

__all__ = [
    # Main API
    "add_storage",
    "easy_storage",
    "get_storage",
    "health_check_storage",
    # Base types
    "StorageBackend",
    "StorageSettings",
    # Backends
    "LocalBackend",
    "MemoryBackend",
    "S3Backend",
    # Exceptions
    "StorageError",
    "FileNotFoundError",
    "PermissionDeniedError",
    "QuotaExceededError",
    "InvalidKeyError",
]
