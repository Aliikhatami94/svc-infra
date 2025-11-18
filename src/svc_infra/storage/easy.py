"""
Easy storage backend builder with auto-detection.

Simplifies storage backend initialization with sensible defaults.
"""

import logging
import os
from typing import Optional

from .backends import LocalBackend, MemoryBackend, S3Backend
from .base import StorageBackend
from .settings import StorageSettings

logger = logging.getLogger(__name__)


def easy_storage(
    backend: Optional[str] = None,
    **kwargs,
) -> StorageBackend:
    """
    Create a storage backend with auto-detection or explicit selection.

    This is the recommended way to initialize storage in most applications.
    It handles environment-based configuration and provides sensible defaults.

    Args:
        backend: Explicit backend type ("local", "s3", "gcs", "cloudinary", "memory")
                If None, auto-detects from environment variables
        **kwargs: Backend-specific configuration overrides

    Returns:
        Initialized storage backend

    Auto-Detection Order:
        1. Explicit backend parameter
        2. STORAGE_BACKEND environment variable
        3. Railway volume (RAILWAY_VOLUME_MOUNT_PATH) → LocalBackend
        4. S3 credentials (AWS_ACCESS_KEY_ID or STORAGE_S3_BUCKET) → S3Backend
        5. GCS credentials (GOOGLE_APPLICATION_CREDENTIALS) → GCSBackend
        6. Cloudinary credentials (CLOUDINARY_URL) → CloudinaryBackend
        7. Default: MemoryBackend (with warning)

    Examples:
        >>> # Auto-detect backend from environment
        >>> storage = easy_storage()
        >>>
        >>> # Explicit local backend
        >>> storage = easy_storage(
        ...     backend="local",
        ...     base_path="/data/uploads"
        ... )
        >>>
        >>> # Explicit S3 backend
        >>> storage = easy_storage(
        ...     backend="s3",
        ...     bucket="my-uploads",
        ...     region="us-west-2"
        ... )
        >>>
        >>> # DigitalOcean Spaces
        >>> storage = easy_storage(
        ...     backend="s3",
        ...     bucket="my-uploads",
        ...     region="nyc3",
        ...     endpoint="https://nyc3.digitaloceanspaces.com"
        ... )

    Environment Variables:
        See StorageSettings for full list of environment variables.

    Raises:
        ValueError: If backend type is unsupported or configuration is invalid
        ImportError: If required backend dependencies are not installed

    Note:
        For production deployments, it's recommended to set STORAGE_BACKEND
        explicitly to avoid unexpected auto-detection behavior.
    """
    # Load settings
    settings = StorageSettings()

    # Determine backend type
    backend_type = backend or settings.detect_backend()

    logger.info(f"Initializing {backend_type} storage backend")

    # Create backend instance
    if backend_type == "memory":
        # Memory backend
        if backend_type == settings.detect_backend() and not backend:
            logger.warning(
                "Using MemoryBackend (in-memory storage). "
                "Data will be lost on restart. "
                "Set STORAGE_BACKEND environment variable for production."
            )

        max_size = kwargs.get("max_size", 100_000_000)
        return MemoryBackend(max_size=max_size)

    elif backend_type == "local":
        # Local filesystem backend
        base_path = kwargs.get("base_path") or settings.storage_base_path

        # Check for Railway volume
        railway_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        if railway_volume and not kwargs.get("base_path"):
            base_path = railway_volume
            logger.info(f"Detected Railway volume at {base_path}")

        base_url = kwargs.get("base_url") or settings.storage_base_url
        signing_secret = kwargs.get("signing_secret") or settings.storage_signing_secret

        return LocalBackend(
            base_path=base_path,
            base_url=base_url,
            signing_secret=signing_secret,
        )

    elif backend_type == "s3":
        # S3-compatible backend
        bucket = kwargs.get("bucket") or settings.storage_s3_bucket
        if not bucket:
            raise ValueError(
                "S3 bucket is required. "
                "Set STORAGE_S3_BUCKET environment variable or pass bucket parameter."
            )

        region = kwargs.get("region") or settings.storage_s3_region
        endpoint = kwargs.get("endpoint") or settings.storage_s3_endpoint

        # Get credentials with fallback
        access_key = kwargs.get("access_key")
        secret_key = kwargs.get("secret_key")

        if not access_key or not secret_key:
            access_key_from_settings, secret_key_from_settings = settings.get_s3_credentials()
            access_key = access_key or access_key_from_settings
            secret_key = secret_key or secret_key_from_settings

        # Log provider detection
        if endpoint:
            if "digitalocean" in endpoint:
                logger.info("Detected DigitalOcean Spaces")
            elif "wasabi" in endpoint:
                logger.info("Detected Wasabi")
            elif "backblaze" in endpoint:
                logger.info("Detected Backblaze B2")
            else:
                logger.info(f"Using custom S3 endpoint: {endpoint}")
        else:
            logger.info("Using AWS S3")

        return S3Backend(
            bucket=bucket,
            region=region,
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
        )

    elif backend_type == "gcs":
        # Google Cloud Storage backend
        raise NotImplementedError(
            "GCS backend not yet implemented. " "Use 'local' or 's3' backend for now."
        )

    elif backend_type == "cloudinary":
        # Cloudinary backend
        raise NotImplementedError(
            "Cloudinary backend not yet implemented. " "Use 'local' or 's3' backend for now."
        )

    else:
        raise ValueError(
            f"Unsupported storage backend: {backend_type}. "
            f"Supported: local, s3, memory (gcs, cloudinary coming soon)"
        )


__all__ = ["easy_storage"]
