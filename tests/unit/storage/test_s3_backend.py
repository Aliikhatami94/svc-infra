"""Unit tests for S3Backend."""

import pytest
import pytest_asyncio

try:
    from botocore.exceptions import ClientError
    from moto import mock_aws

    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False
    mock_aws = None
    ClientError = Exception

try:
    import aioboto3

    AIOBOTO3_AVAILABLE = True
except ImportError:
    AIOBOTO3_AVAILABLE = False

from svc_infra.storage.backends.s3 import S3Backend
from svc_infra.storage.base import (
    FileNotFoundError,
    InvalidKeyError,
    PermissionDeniedError,
    StorageError,
)


@pytest.mark.storage
@pytest.mark.asyncio
@pytest.mark.skip(
    reason="moto does not support aiobotocore async operations - use integration tests for S3"
)
class TestS3Backend:
    """Test suite for S3Backend with mocked S3.

    Note: These tests are skipped because moto's mock_aws doesn't fully support
    aiobotocore's async operations (MockRawResponse missing raw_headers attribute).
    S3 backend functionality should be tested with integration tests against real S3
    or S3-compatible services (LocalStack, MinIO).
    """

    @pytest_asyncio.fixture
    async def s3_backend(self):
        """Create S3Backend with mocked S3."""
        with mock_aws():
            # Create backend
            backend = S3Backend(
                bucket="test-bucket",
                region="us-east-1",
                access_key="test-access-key",
                secret_key="test-secret-key",
            )

            # Create bucket
            import aioboto3

            session = aioboto3.Session()
            async with session.client(
                "s3",
                region_name="us-east-1",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",
            ) as s3:
                await s3.create_bucket(Bucket="test-bucket")

            yield backend

    async def test_put_and_get(self, s3_backend):
        """Test basic file storage and retrieval."""
        # Put file
        url = await s3_backend.put(
            key="test/file.txt",
            data=b"Hello, World!",
            content_type="text/plain",
        )

        assert "test/file.txt" in url

        # Get file
        data = await s3_backend.get("test/file.txt")
        assert data == b"Hello, World!"

    async def test_put_with_metadata(self, s3_backend):
        """Test storing file with metadata."""
        await s3_backend.put(
            key="test/file.txt",
            data=b"test data",
            content_type="application/json",
            metadata={"user_id": "user_123", "version": "1.0"},
        )

        # Get metadata
        metadata = await s3_backend.get_metadata("test/file.txt")
        assert metadata["user_id"] == "user_123"
        assert metadata["version"] == "1.0"
        assert metadata["size"] == 9
        assert metadata["content_type"] == "application/json"

    async def test_get_nonexistent_file(self, s3_backend):
        """Test getting a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await s3_backend.get("nonexistent.txt")

    async def test_delete(self, s3_backend):
        """Test file deletion."""
        # Put file
        await s3_backend.put("test/file.txt", b"data", "text/plain")

        # Verify exists
        assert await s3_backend.exists("test/file.txt")

        # Delete
        deleted = await s3_backend.delete("test/file.txt")
        assert deleted is True

        # Verify doesn't exist
        assert not await s3_backend.exists("test/file.txt")

    async def test_delete_nonexistent(self, s3_backend):
        """Test deleting a file that doesn't exist."""
        deleted = await s3_backend.delete("nonexistent.txt")
        assert deleted is False

    async def test_exists(self, s3_backend):
        """Test file existence check."""
        assert not await s3_backend.exists("test/file.txt")

        await s3_backend.put("test/file.txt", b"data", "text/plain")

        assert await s3_backend.exists("test/file.txt")

    async def test_get_url_presigned(self, s3_backend):
        """Test presigned URL generation."""
        await s3_backend.put("test/file.txt", b"data", "text/plain")

        url = await s3_backend.get_url("test/file.txt", expires_in=3600)

        # Check URL structure (presigned URLs have specific format)
        assert "test/file.txt" in url
        assert "X-Amz" in url or "Signature" in url  # AWS signature

    async def test_get_url_with_download(self, s3_backend):
        """Test URL generation with download flag."""
        await s3_backend.put("test/document.pdf", b"pdf data", "application/pdf")

        url = await s3_backend.get_url("test/document.pdf", download=True)

        # Should include Content-Disposition parameter
        assert "response-content-disposition" in url.lower()

    async def test_get_url_nonexistent(self, s3_backend):
        """Test URL generation for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            await s3_backend.get_url("nonexistent.txt")

    async def test_list_keys_empty(self, s3_backend):
        """Test listing keys when storage is empty."""
        keys = await s3_backend.list_keys()
        assert keys == []

    async def test_list_keys(self, s3_backend):
        """Test listing all keys."""
        await s3_backend.put("file1.txt", b"data1", "text/plain")
        await s3_backend.put("file2.txt", b"data2", "text/plain")
        await s3_backend.put("dir/file3.txt", b"data3", "text/plain")

        keys = await s3_backend.list_keys()
        assert len(keys) == 3
        assert "file1.txt" in keys
        assert "file2.txt" in keys
        assert "dir/file3.txt" in keys

    async def test_list_keys_with_prefix(self, s3_backend):
        """Test listing keys with prefix filter."""
        await s3_backend.put("avatars/user1.jpg", b"img1", "image/jpeg")
        await s3_backend.put("avatars/user2.jpg", b"img2", "image/jpeg")
        await s3_backend.put("documents/doc1.pdf", b"pdf1", "application/pdf")

        keys = await s3_backend.list_keys(prefix="avatars/")
        assert len(keys) == 2
        assert all(k.startswith("avatars/") for k in keys)

    async def test_list_keys_with_limit(self, s3_backend):
        """Test listing keys with limit."""
        for i in range(10):
            await s3_backend.put(f"file{i}.txt", b"data", "text/plain")

        keys = await s3_backend.list_keys(limit=5)
        assert len(keys) == 5

    async def test_get_metadata(self, s3_backend):
        """Test retrieving file metadata."""
        await s3_backend.put(
            key="test/file.txt",
            data=b"test data",
            content_type="text/plain",
            metadata={"custom": "value"},
        )

        metadata = await s3_backend.get_metadata("test/file.txt")
        assert metadata["size"] == 9
        assert metadata["content_type"] == "text/plain"
        assert metadata["custom"] == "value"
        assert "created_at" in metadata

    async def test_get_metadata_nonexistent(self, s3_backend):
        """Test getting metadata for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            await s3_backend.get_metadata("nonexistent.txt")

    async def test_invalid_key_validation(self, s3_backend):
        """Test key validation."""
        # Empty key
        with pytest.raises(InvalidKeyError):
            await s3_backend.put("", b"data", "text/plain")

        # Leading slash
        with pytest.raises(InvalidKeyError):
            await s3_backend.put("/file.txt", b"data", "text/plain")

        # Path traversal
        with pytest.raises(InvalidKeyError):
            await s3_backend.put("../etc/passwd", b"data", "text/plain")

        # Too long
        with pytest.raises(InvalidKeyError):
            await s3_backend.put("x" * 1025, b"data", "text/plain")

    async def test_binary_data(self, s3_backend):
        """Test storing binary data."""
        binary_data = bytes(range(256))

        await s3_backend.put("binary.bin", binary_data, "application/octet-stream")

        retrieved = await s3_backend.get("binary.bin")
        assert retrieved == binary_data

    async def test_custom_endpoint(self):
        """Test S3Backend with custom endpoint (DigitalOcean Spaces example)."""
        with mock_aws():
            backend = S3Backend(
                bucket="test-bucket",
                region="nyc3",
                endpoint="https://nyc3.digitaloceanspaces.com",
                access_key="test-key",
                secret_key="test-secret",
            )

            assert backend.endpoint == "https://nyc3.digitaloceanspaces.com"
            assert backend.region == "nyc3"


@pytest.mark.storage
@pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
class TestS3BackendInit:
    """Test S3Backend initialization without mocking."""

    def test_init_with_credentials(self):
        """Test initialization with explicit credentials."""
        backend = S3Backend(
            bucket="my-bucket",
            region="us-west-2",
            access_key="access-key",
            secret_key="secret-key",
        )

        assert backend.bucket == "my-bucket"
        assert backend.region == "us-west-2"
        assert backend.access_key == "access-key"
        assert backend.secret_key == "secret-key"

    def test_init_without_credentials(self):
        """Test initialization without explicit credentials (uses env vars)."""
        backend = S3Backend(
            bucket="my-bucket",
            region="eu-west-1",
        )

        assert backend.bucket == "my-bucket"
        assert backend.region == "eu-west-1"
        assert backend.access_key is None
        assert backend.secret_key is None

    def test_init_digitalocean_spaces(self):
        """Test initialization for DigitalOcean Spaces."""
        backend = S3Backend(
            bucket="my-spaces-bucket",
            region="nyc3",
            endpoint="https://nyc3.digitaloceanspaces.com",
            access_key="do-access-key",
            secret_key="do-secret-key",
        )

        assert backend.bucket == "my-spaces-bucket"
        assert backend.region == "nyc3"
        assert backend.endpoint == "https://nyc3.digitaloceanspaces.com"

    def test_init_wasabi(self):
        """Test initialization for Wasabi."""
        backend = S3Backend(
            bucket="my-wasabi-bucket",
            region="us-east-1",
            endpoint="https://s3.wasabisys.com",
            access_key="wasabi-key",
            secret_key="wasabi-secret",
        )

        assert backend.endpoint == "https://s3.wasabisys.com"

    def test_aioboto3_not_installed(self, monkeypatch):
        """Test error when aioboto3 is not installed."""
        # Mock aioboto3 as not available by patching the module
        import svc_infra.storage.backends.s3 as s3_module

        original = s3_module.aioboto3
        monkeypatch.setattr(s3_module, "aioboto3", None)

        # This should raise ImportError when aioboto3 is None
        with pytest.raises(ImportError, match="aioboto3"):
            S3Backend(bucket="test", region="us-east-1")

        # Restore original
        monkeypatch.setattr(s3_module, "aioboto3", original)


@pytest.mark.storage
@pytest.mark.integration
@pytest.mark.skipif(
    not MOTO_AVAILABLE, reason="Integration tests require moto and real AWS credentials"
)
class TestS3BackendIntegration:
    """
    Integration tests with real S3 (or moto).

    These tests are skipped in CI unless AWS credentials are available.
    Mark with @pytest.mark.integration to skip in regular test runs.
    """

    @pytest_asyncio.fixture
    async def real_s3_backend(self):
        """Create S3Backend with real AWS credentials from environment."""
        import os

        bucket = os.getenv("TEST_S3_BUCKET")
        region = os.getenv("TEST_S3_REGION", "us-east-1")

        if not bucket:
            pytest.skip("TEST_S3_BUCKET not set")

        backend = S3Backend(bucket=bucket, region=region)

        yield backend

        # Cleanup: delete test files
        try:
            keys = await backend.list_keys(prefix="test-storage/")
            for key in keys:
                await backend.delete(key)
        except Exception:
            pass  # Best effort cleanup

    async def test_real_s3_operations(self, real_s3_backend):
        """Test operations against real S3."""
        key = "test-storage/integration-test.txt"

        # Put
        await real_s3_backend.put(key, b"integration test data", "text/plain")

        # Exists
        assert await real_s3_backend.exists(key)

        # Get
        data = await real_s3_backend.get(key)
        assert data == b"integration test data"

        # Delete
        await real_s3_backend.delete(key)
        assert not await real_s3_backend.exists(key)
