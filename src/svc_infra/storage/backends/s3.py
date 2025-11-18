"""
S3-compatible storage backend.

Works with AWS S3, DigitalOcean Spaces, Wasabi, Backblaze B2, Minio, and
any S3-compatible object storage service.
"""

from typing import Optional

try:
    import aioboto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    aioboto3 = None  # type: ignore
    ClientError = Exception  # type: ignore
    NoCredentialsError = Exception  # type: ignore

from ..base import FileNotFoundError, InvalidKeyError, PermissionDeniedError, StorageError


class S3Backend:
    """
    S3-compatible storage backend.

    Supports AWS S3, DigitalOcean Spaces, Wasabi, Backblaze B2, Minio,
    and any S3-compatible object storage.

    Args:
        bucket: S3 bucket name
        region: AWS region (default: "us-east-1")
        endpoint: Custom endpoint URL for S3-compatible services
        access_key: AWS access key (uses AWS_ACCESS_KEY_ID env var if not provided)
        secret_key: AWS secret key (uses AWS_SECRET_ACCESS_KEY env var if not provided)

    Example:
        >>> # AWS S3
        >>> backend = S3Backend(
        ...     bucket="my-uploads",
        ...     region="us-west-2"
        ... )
        >>>
        >>> # DigitalOcean Spaces
        >>> backend = S3Backend(
        ...     bucket="my-uploads",
        ...     region="nyc3",
        ...     endpoint="https://nyc3.digitaloceanspaces.com",
        ...     access_key="...",
        ...     secret_key="..."
        ... )
        >>>
        >>> # Wasabi
        >>> backend = S3Backend(
        ...     bucket="my-uploads",
        ...     region="us-east-1",
        ...     endpoint="https://s3.wasabisys.com"
        ... )

    Raises:
        ImportError: If aioboto3 is not installed
    """

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        if aioboto3 is None:
            raise ImportError(
                "aioboto3 is required for S3Backend. " "Install it with: pip install aioboto3"
            )

        self.bucket = bucket
        self.region = region
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key

        # Session configuration
        self._session_config = {
            "region_name": region,
        }
        if endpoint:
            self._session_config["endpoint_url"] = endpoint

        # Client configuration
        self._client_config = {}
        if access_key and secret_key:
            self._client_config = {
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
            }

    def _validate_key(self, key: str) -> None:
        """Validate storage key format."""
        if not key:
            raise InvalidKeyError("Key cannot be empty")

        if key.startswith("/"):
            raise InvalidKeyError("Key cannot start with /")

        if ".." in key:
            raise InvalidKeyError("Key cannot contain .. (path traversal)")

        if len(key) > 1024:
            raise InvalidKeyError("Key cannot exceed 1024 characters")

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store file in S3."""
        self._validate_key(key)

        # Prepare S3 metadata (must be string key-value pairs)
        s3_metadata = {}
        if metadata:
            for k, v in metadata.items():
                s3_metadata[str(k)] = str(v)

        try:
            session = aioboto3.Session()
            async with session.client("s3", **self._session_config, **self._client_config) as s3:
                # Upload file
                await s3.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                    Metadata=s3_metadata,
                )

        except NoCredentialsError as e:
            raise PermissionDeniedError(f"S3 credentials not found: {e}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AccessDenied":
                raise PermissionDeniedError(f"S3 access denied: {e}")
            elif error_code == "NoSuchBucket":
                raise StorageError(f"S3 bucket does not exist: {self.bucket}")
            else:
                raise StorageError(f"S3 upload failed: {e}")
        except Exception as e:
            raise StorageError(f"Failed to upload to S3: {e}")

        # Return presigned URL (1 hour expiration)
        return await self.get_url(key, expires_in=3600)

    async def get(self, key: str) -> bytes:
        """Retrieve file from S3."""
        self._validate_key(key)

        try:
            session = aioboto3.Session()
            async with session.client("s3", **self._session_config, **self._client_config) as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {key}")
            elif error_code == "AccessDenied":
                raise PermissionDeniedError(f"S3 access denied: {e}")
            else:
                raise StorageError(f"S3 download failed: {e}")
        except Exception as e:
            raise StorageError(f"Failed to download from S3: {e}")

    async def delete(self, key: str) -> bool:
        """Delete file from S3."""
        self._validate_key(key)

        # Check if file exists first
        if not await self.exists(key):
            return False

        try:
            session = aioboto3.Session()
            async with session.client("s3", **self._session_config, **self._client_config) as s3:
                await s3.delete_object(Bucket=self.bucket, Key=key)
                return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AccessDenied":
                raise PermissionDeniedError(f"S3 access denied: {e}")
            else:
                raise StorageError(f"S3 delete failed: {e}")
        except Exception as e:
            raise StorageError(f"Failed to delete from S3: {e}")

    async def exists(self, key: str) -> bool:
        """Check if file exists in S3."""
        self._validate_key(key)

        try:
            session = aioboto3.Session()
            async with session.client("s3", **self._session_config, **self._client_config) as s3:
                await s3.head_object(Bucket=self.bucket, Key=key)
                return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ("NoSuchKey", "404"):
                return False
            else:
                raise StorageError(f"S3 head_object failed: {e}")
        except Exception as e:
            raise StorageError(f"Failed to check S3 file existence: {e}")

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
        download: bool = False,
    ) -> str:
        """
        Generate presigned URL for file access.

        Args:
            key: Storage key
            expires_in: URL expiration in seconds (default: 1 hour)
            download: If True, force download instead of inline display

        Returns:
            Presigned S3 URL

        Example:
            >>> url = await backend.get_url("documents/invoice.pdf", expires_in=300)
        """
        self._validate_key(key)

        # Check if file exists
        if not await self.exists(key):
            raise FileNotFoundError(f"File not found: {key}")

        try:
            session = aioboto3.Session()
            async with session.client("s3", **self._session_config, **self._client_config) as s3:
                # Prepare parameters
                params = {"Bucket": self.bucket, "Key": key}

                # Add Content-Disposition for downloads
                if download:
                    # Extract filename from key
                    filename = key.split("/")[-1]
                    params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

                # Generate presigned URL
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params=params,
                    ExpiresIn=expires_in,
                )
                return url

        except ClientError as e:
            raise StorageError(f"Failed to generate presigned URL: {e}")
        except Exception as e:
            raise StorageError(f"Failed to generate presigned URL: {e}")

    async def list_keys(
        self,
        prefix: str = "",
        limit: int = 100,
    ) -> list[str]:
        """List stored keys with optional prefix filter."""
        try:
            session = aioboto3.Session()
            async with session.client("s3", **self._session_config, **self._client_config) as s3:
                params = {
                    "Bucket": self.bucket,
                    "MaxKeys": limit,
                }
                if prefix:
                    params["Prefix"] = prefix

                response = await s3.list_objects_v2(**params)

                # Extract keys from response
                contents = response.get("Contents", [])
                keys = [obj["Key"] for obj in contents]
                return keys

        except ClientError as e:
            raise StorageError(f"S3 list failed: {e}")
        except Exception as e:
            raise StorageError(f"Failed to list S3 keys: {e}")

    async def get_metadata(self, key: str) -> dict:
        """Get file metadata from S3."""
        self._validate_key(key)

        try:
            session = aioboto3.Session()
            async with session.client("s3", **self._session_config, **self._client_config) as s3:
                response = await s3.head_object(Bucket=self.bucket, Key=key)

                # Extract metadata
                metadata = {
                    "size": response["ContentLength"],
                    "content_type": response.get("ContentType", "application/octet-stream"),
                    "created_at": response["LastModified"].isoformat(),
                }

                # Add custom metadata
                if "Metadata" in response:
                    metadata.update(response["Metadata"])

                return metadata

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {key}")
            else:
                raise StorageError(f"S3 head_object failed: {e}")
        except Exception as e:
            raise StorageError(f"Failed to get S3 metadata: {e}")


__all__ = ["S3Backend"]
