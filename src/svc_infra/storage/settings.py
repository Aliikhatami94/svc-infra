"""
Storage configuration and settings.

Handles environment-based configuration and auto-detection of storage backends.
"""

import os
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class StorageSettings(BaseSettings):
    """
    Storage system configuration.

    Supports multiple backends with auto-detection from environment variables.

    Environment Variables:
        STORAGE_BACKEND: Explicit backend selection ("local", "s3", "gcs", "cloudinary", "memory")

        Local Backend:
            STORAGE_BASE_PATH: Base directory for file storage (default: /data/uploads)
            STORAGE_BASE_URL: Base URL for file serving (default: http://localhost:8000/files)
            STORAGE_SIGNING_SECRET: Secret key for URL signing (auto-generated if not set)

        S3 Backend:
            STORAGE_S3_BUCKET: S3 bucket name (required for S3)
            STORAGE_S3_REGION: AWS region (default: us-east-1)
            STORAGE_S3_ENDPOINT: Custom endpoint for S3-compatible services (optional)
            STORAGE_S3_ACCESS_KEY: AWS access key (optional, uses AWS_ACCESS_KEY_ID if not set)
            STORAGE_S3_SECRET_KEY: AWS secret key (optional, uses AWS_SECRET_ACCESS_KEY if not set)

        GCS Backend:
            STORAGE_GCS_BUCKET: GCS bucket name (required for GCS)
            STORAGE_GCS_PROJECT: GCP project ID (optional)
            STORAGE_GCS_CREDENTIALS_PATH: Path to service account JSON (optional)

        Cloudinary Backend:
            STORAGE_CLOUDINARY_CLOUD_NAME: Cloudinary cloud name (required)
            STORAGE_CLOUDINARY_API_KEY: Cloudinary API key (required)
            STORAGE_CLOUDINARY_API_SECRET: Cloudinary API secret (required)

    Example:
        >>> # Auto-detect backend from environment
        >>> settings = StorageSettings()
        >>> backend = settings.detect_backend()
        >>>
        >>> # Explicit backend selection
        >>> settings = StorageSettings(storage_backend="s3")
    """

    # Backend selection
    storage_backend: Optional[Literal["local", "s3", "gcs", "cloudinary", "memory"]] = Field(
        default=None,
        description="Storage backend type (auto-detected if not set)",
    )

    # Local backend settings
    storage_base_path: str = Field(
        default="/data/uploads",
        description="Base directory for local file storage",
    )
    storage_base_url: str = Field(
        default="http://localhost:8000/files",
        description="Base URL for serving files",
    )
    storage_signing_secret: Optional[str] = Field(
        default=None,
        description="Secret key for URL signing (auto-generated if not set)",
    )

    # S3 backend settings
    storage_s3_bucket: Optional[str] = Field(
        default=None,
        description="S3 bucket name",
    )
    storage_s3_region: str = Field(
        default="us-east-1",
        description="AWS region",
    )
    storage_s3_endpoint: Optional[str] = Field(
        default=None,
        description="Custom S3 endpoint (for DigitalOcean Spaces, Wasabi, etc.)",
    )
    storage_s3_access_key: Optional[str] = Field(
        default=None,
        description="S3 access key (falls back to AWS_ACCESS_KEY_ID)",
    )
    storage_s3_secret_key: Optional[str] = Field(
        default=None,
        description="S3 secret key (falls back to AWS_SECRET_ACCESS_KEY)",
    )

    # GCS backend settings
    storage_gcs_bucket: Optional[str] = Field(
        default=None,
        description="Google Cloud Storage bucket name",
    )
    storage_gcs_project: Optional[str] = Field(
        default=None,
        description="GCP project ID",
    )
    storage_gcs_credentials_path: Optional[str] = Field(
        default=None,
        description="Path to GCP service account JSON",
    )

    # Cloudinary backend settings
    storage_cloudinary_cloud_name: Optional[str] = Field(
        default=None,
        description="Cloudinary cloud name",
    )
    storage_cloudinary_api_key: Optional[str] = Field(
        default=None,
        description="Cloudinary API key",
    )
    storage_cloudinary_api_secret: Optional[str] = Field(
        default=None,
        description="Cloudinary API secret",
    )

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",  # Ignore unknown environment variables
    }

    def detect_backend(self) -> str:
        """
        Auto-detect storage backend from environment.

        Detection order:
            1. Explicit STORAGE_BACKEND setting
            2. Railway volume (RAILWAY_VOLUME_MOUNT_PATH) → local
            3. S3 credentials (AWS_ACCESS_KEY_ID or STORAGE_S3_BUCKET) → s3
            4. GCS credentials (GOOGLE_APPLICATION_CREDENTIALS or STORAGE_GCS_BUCKET) → gcs
            5. Cloudinary credentials (CLOUDINARY_URL or STORAGE_CLOUDINARY_CLOUD_NAME) → cloudinary
            6. Default → memory (with warning)

        Returns:
            Backend type string

        Example:
            >>> settings = StorageSettings()
            >>> backend_type = settings.detect_backend()
            >>> print(f"Using {backend_type} backend")
        """
        # Explicit setting takes precedence
        if self.storage_backend:
            return self.storage_backend

        # Check for Railway volume
        railway_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        if railway_volume:
            return "local"

        # Check for S3
        has_s3_key = os.getenv("AWS_ACCESS_KEY_ID") or self.storage_s3_access_key
        if has_s3_key or self.storage_s3_bucket:
            return "s3"

        # Check for GCS
        has_gcs_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if has_gcs_creds or self.storage_gcs_bucket:
            return "gcs"

        # Check for Cloudinary
        has_cloudinary = os.getenv("CLOUDINARY_URL")
        if has_cloudinary or self.storage_cloudinary_cloud_name:
            return "cloudinary"

        # Default to memory (for development/testing)
        return "memory"

    def get_s3_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """
        Get S3 credentials with fallback to AWS environment variables.

        Returns:
            Tuple of (access_key, secret_key)

        Example:
            >>> settings = StorageSettings()
            >>> access_key, secret_key = settings.get_s3_credentials()
        """
        access_key = self.storage_s3_access_key or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = self.storage_s3_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        return access_key, secret_key


__all__ = ["StorageSettings"]
