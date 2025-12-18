"""Integration tests for S3 storage backend.

These tests require S3 credentials to be set:
- AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY: AWS credentials
- STORAGE_S3_BUCKET: S3 bucket name (required for S3 tests)

Alternatively, for local testing with MinIO:
- STORAGE_S3_ENDPOINT: MinIO endpoint (e.g., http://localhost:9000)

Run with: pytest tests/integration/test_storage_s3.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest

# Check if aioboto3 is available
try:
    import aioboto3  # noqa: F401

    HAS_AIOBOTO3 = True
except ImportError:
    HAS_AIOBOTO3 = False

# Skip markers
SKIP_NO_S3_CREDS = pytest.mark.skipif(
    not (
        os.environ.get("STORAGE_S3_BUCKET")
        and (
            os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("STORAGE_S3_ACCESS_KEY")
        )
    ),
    reason="S3 credentials not configured",
)

SKIP_NO_AIOBOTO3 = pytest.mark.skipif(
    not HAS_AIOBOTO3,
    reason="aioboto3 package not installed",
)


# =============================================================================
# Local Storage Backend Tests (No Cloud Required)
# =============================================================================


@pytest.mark.integration
class TestLocalStorageBackend:
    """Integration tests for local filesystem storage backend."""

    @pytest.fixture
    def local_storage(self, tmp_path):
        """Create a local storage backend with temp directory."""
        from svc_infra.storage.backends.local import LocalBackend

        return LocalBackend(
            base_path=str(tmp_path / "uploads"),
            base_url="http://localhost:8000/files",
        )

    @pytest.mark.asyncio
    async def test_put_and_get_file(self, local_storage):
        """Test uploading and retrieving a file."""
        content = b"Hello, World!"
        key = "test/hello.txt"

        # Upload
        url = await local_storage.put(
            key=key,
            data=content,
            content_type="text/plain",
            metadata={"uploaded_by": "test"},
        )

        assert url.startswith("http://localhost:8000/files/")
        assert key in url

        # Retrieve
        retrieved = await local_storage.get(key)
        assert retrieved == content

    @pytest.mark.asyncio
    async def test_delete_file(self, local_storage):
        """Test deleting a file."""
        content = b"Delete me"
        key = "test/delete_me.txt"

        # Upload
        await local_storage.put(key=key, data=content, content_type="text/plain")

        # Delete
        await local_storage.delete(key)

        # Verify deleted
        from svc_infra.storage.base import FileNotFoundError

        with pytest.raises(FileNotFoundError):
            await local_storage.get(key)

    @pytest.mark.asyncio
    async def test_exists(self, local_storage):
        """Test checking if file exists."""
        key = "test/exists.txt"

        # Should not exist yet
        assert not await local_storage.exists(key)

        # Upload
        await local_storage.put(key=key, data=b"exists", content_type="text/plain")

        # Should exist now
        assert await local_storage.exists(key)

    @pytest.mark.asyncio
    async def test_list_files(self, local_storage):
        """Test listing files with prefix."""
        # Upload multiple files
        for i in range(3):
            await local_storage.put(
                key=f"list_test/file_{i}.txt",
                data=f"Content {i}".encode(),
                content_type="text/plain",
            )

        # List files
        files = await local_storage.list(prefix="list_test/")

        assert len(files) == 3
        assert all("list_test/file_" in f for f in files)

    @pytest.mark.asyncio
    async def test_invalid_key_rejected(self, local_storage):
        """Test that path traversal attempts are rejected."""
        from svc_infra.storage.base import InvalidKeyError

        with pytest.raises(InvalidKeyError):
            await local_storage.put(
                key="../../../etc/passwd",
                data=b"malicious",
                content_type="text/plain",
            )


# =============================================================================
# Memory Storage Backend Tests
# =============================================================================


@pytest.mark.integration
class TestMemoryStorageBackend:
    """Integration tests for in-memory storage backend."""

    @pytest.fixture
    def memory_storage(self):
        """Create an in-memory storage backend."""
        from svc_infra.storage.backends.memory import MemoryBackend

        return MemoryBackend(base_url="http://localhost:8000/files")

    @pytest.mark.asyncio
    async def test_put_and_get_file(self, memory_storage):
        """Test uploading and retrieving a file."""
        content = b"Memory test content"
        key = "memory/test.txt"

        url = await memory_storage.put(
            key=key,
            data=content,
            content_type="text/plain",
        )

        assert key in url

        retrieved = await memory_storage.get(key)
        assert retrieved == content

    @pytest.mark.asyncio
    async def test_metadata_preserved(self, memory_storage):
        """Test that metadata is preserved."""
        content = b"With metadata"
        key = "memory/metadata.txt"
        metadata = {"user_id": "123", "purpose": "test"}

        await memory_storage.put(
            key=key,
            data=content,
            content_type="text/plain",
            metadata=metadata,
        )

        info = await memory_storage.info(key)
        assert info["metadata"]["user_id"] == "123"
        assert info["metadata"]["purpose"] == "test"


# =============================================================================
# S3 Storage Backend Tests (Requires Credentials)
# =============================================================================


@SKIP_NO_AIOBOTO3
@SKIP_NO_S3_CREDS
@pytest.mark.integration
class TestS3StorageBackend:
    """Integration tests for S3 storage backend.

    These tests require real S3 credentials and a bucket.
    Consider using LocalStack or MinIO for local testing.
    """

    @pytest.fixture
    def s3_storage(self):
        """Create S3 storage backend from environment."""
        from svc_infra.storage.backends.s3 import S3Backend

        return S3Backend(
            bucket=os.environ["STORAGE_S3_BUCKET"],
            region=os.environ.get("STORAGE_S3_REGION", "us-east-1"),
            endpoint=os.environ.get("STORAGE_S3_ENDPOINT"),
            access_key=os.environ.get("STORAGE_S3_ACCESS_KEY"),
            secret_key=os.environ.get("STORAGE_S3_SECRET_KEY"),
        )

    @pytest.fixture
    def test_key_prefix(self):
        """Generate unique prefix for test files to avoid conflicts."""
        return f"integration-tests/{uuid.uuid4().hex[:8]}"

    @pytest.mark.asyncio
    async def test_put_and_get_file(self, s3_storage, test_key_prefix):
        """Test uploading and retrieving a file from S3."""
        content = b"S3 test content"
        key = f"{test_key_prefix}/test.txt"

        try:
            # Upload
            url = await s3_storage.put(
                key=key,
                data=content,
                content_type="text/plain",
                metadata={"test": "true"},
            )

            assert url is not None

            # Retrieve
            retrieved = await s3_storage.get(key)
            assert retrieved == content

        finally:
            # Cleanup
            try:
                await s3_storage.delete(key)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_large_file_upload(self, s3_storage, test_key_prefix):
        """Test uploading a larger file (1MB)."""
        content = b"x" * (1024 * 1024)  # 1MB
        key = f"{test_key_prefix}/large_file.bin"

        try:
            url = await s3_storage.put(
                key=key,
                data=content,
                content_type="application/octet-stream",
            )

            assert url is not None

            # Verify size
            info = await s3_storage.info(key)
            assert info["size"] == len(content)

        finally:
            try:
                await s3_storage.delete(key)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_presigned_url(self, s3_storage, test_key_prefix):
        """Test generating presigned URLs for download."""
        content = b"Presigned content"
        key = f"{test_key_prefix}/presigned.txt"

        try:
            await s3_storage.put(
                key=key,
                data=content,
                content_type="text/plain",
            )

            # Generate presigned URL
            presigned_url = await s3_storage.get_url(key, expires_in=3600)

            assert presigned_url is not None
            assert key in presigned_url or "Signature" in presigned_url

        finally:
            try:
                await s3_storage.delete(key)
            except Exception:
                pass


# =============================================================================
# Easy Storage Factory Tests
# =============================================================================


@pytest.mark.integration
class TestEasyStorageFactory:
    """Integration tests for easy_storage factory function."""

    def test_easy_storage_local(self, tmp_path):
        """Test creating local storage backend."""
        from svc_infra.storage import easy_storage

        storage = easy_storage(
            backend="local",
            base_path=str(tmp_path / "uploads"),
            base_url="http://localhost:8000/files",
        )

        from svc_infra.storage.backends.local import LocalBackend

        assert isinstance(storage, LocalBackend)

    def test_easy_storage_memory(self):
        """Test creating memory storage backend."""
        from svc_infra.storage import easy_storage

        storage = easy_storage(backend="memory")

        from svc_infra.storage.backends.memory import MemoryBackend

        assert isinstance(storage, MemoryBackend)

    @SKIP_NO_AIOBOTO3
    def test_easy_storage_s3_without_bucket_fails(self):
        """Test that S3 backend requires bucket configuration."""
        from svc_infra.storage import easy_storage

        # Clear bucket env var temporarily
        bucket = os.environ.pop("STORAGE_S3_BUCKET", None)

        try:
            with pytest.raises((ValueError, KeyError)):
                easy_storage(backend="s3")
        finally:
            if bucket:
                os.environ["STORAGE_S3_BUCKET"] = bucket

    def test_easy_storage_invalid_backend(self):
        """Test error handling for invalid backend."""
        from svc_infra.storage import easy_storage

        with pytest.raises(ValueError, match="Unknown storage backend"):
            easy_storage(backend="invalid_backend")


# =============================================================================
# Storage Add Helper Tests
# =============================================================================


@pytest.mark.integration
class TestAddStorageHelper:
    """Integration tests for add_storage FastAPI helper."""

    def test_add_storage_to_app(self, tmp_path):
        """Test adding storage to FastAPI app."""
        from fastapi import FastAPI
        from svc_infra.storage import add_storage

        app = FastAPI()

        storage = add_storage(
            app,
            backend="local",
            base_path=str(tmp_path / "uploads"),
            base_url="http://localhost:8000/files",
        )

        # Storage should be on app.state
        assert hasattr(app.state, "storage")
        assert app.state.storage is storage

    @pytest.mark.asyncio
    async def test_storage_dependency_injection(self, tmp_path):
        """Test storage dependency injection in routes."""
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient
        from svc_infra.storage import add_storage, get_storage, StorageBackend

        app = FastAPI()

        add_storage(
            app,
            backend="local",
            base_path=str(tmp_path / "uploads"),
            base_url="http://localhost:8000/files",
        )

        @app.get("/test-storage")
        async def test_route(storage: StorageBackend = Depends(get_storage)):
            return {"has_storage": storage is not None}

        client = TestClient(app)
        response = client.get("/test-storage")

        assert response.status_code == 200
        assert response.json()["has_storage"] is True
