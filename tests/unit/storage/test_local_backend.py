"""Unit tests for LocalBackend."""

import json
import tempfile

import pytest
import pytest_asyncio

from svc_infra.storage.backends.local import LocalBackend
from svc_infra.storage.base import FileNotFoundError, InvalidKeyError


@pytest.mark.storage
@pytest.mark.asyncio
class TestLocalBackend:
    """Test suite for LocalBackend."""

    @pytest_asyncio.fixture
    async def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest_asyncio.fixture
    async def backend(self, temp_dir):
        """Create LocalBackend instance with temp directory."""
        return LocalBackend(
            base_path=temp_dir,
            base_url="http://localhost:8000/files",
            signing_secret="test-secret-key",
        )

    async def test_put_and_get(self, backend):
        """Test basic file storage and retrieval."""
        # Put file
        url = await backend.put(
            key="test/file.txt",
            data=b"Hello, World!",
            content_type="text/plain",
        )

        assert "test/file.txt" in url
        assert "expires=" in url
        assert "signature=" in url

        # Get file
        data = await backend.get("test/file.txt")
        assert data == b"Hello, World!"

    async def test_put_creates_directories(self, backend):
        """Test that put creates parent directories."""
        await backend.put(
            key="deep/nested/path/file.txt",
            data=b"data",
            content_type="text/plain",
        )

        # Verify file exists
        file_path = backend._get_file_path("deep/nested/path/file.txt")
        assert file_path.exists()
        assert file_path.is_file()

    async def test_put_with_metadata(self, backend):
        """Test storing file with metadata."""
        await backend.put(
            key="test/file.txt",
            data=b"test data",
            content_type="application/json",
            metadata={"user_id": "user_123", "version": "1.0"},
        )

        # Check metadata file
        meta_path = backend._get_metadata_path("test/file.txt")
        assert meta_path.exists()

        with open(meta_path) as f:
            metadata = json.load(f)

        assert metadata["user_id"] == "user_123"
        assert metadata["version"] == "1.0"
        assert metadata["size"] == 9
        assert metadata["content_type"] == "application/json"
        assert "created_at" in metadata

    async def test_get_nonexistent_file(self, backend):
        """Test getting a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await backend.get("nonexistent.txt")

    async def test_delete(self, backend):
        """Test file deletion."""
        # Put file
        await backend.put("test/file.txt", b"data", "text/plain")

        # Verify exists
        assert await backend.exists("test/file.txt")

        # Delete
        deleted = await backend.delete("test/file.txt")
        assert deleted is True

        # Verify doesn't exist
        assert not await backend.exists("test/file.txt")

    async def test_delete_removes_metadata(self, backend):
        """Test that delete also removes metadata file."""
        await backend.put("test/file.txt", b"data", "text/plain")

        meta_path = backend._get_metadata_path("test/file.txt")
        assert meta_path.exists()

        await backend.delete("test/file.txt")

        assert not meta_path.exists()

    async def test_delete_nonexistent(self, backend):
        """Test deleting a file that doesn't exist."""
        deleted = await backend.delete("nonexistent.txt")
        assert deleted is False

    async def test_exists(self, backend):
        """Test file existence check."""
        assert not await backend.exists("test/file.txt")

        await backend.put("test/file.txt", b"data", "text/plain")

        assert await backend.exists("test/file.txt")

    async def test_get_url_signed(self, backend):
        """Test signed URL generation."""
        await backend.put("test/file.txt", b"data", "text/plain")

        url = await backend.get_url("test/file.txt", expires_in=3600)

        # Check URL structure
        assert url.startswith("http://localhost:8000/files/")
        assert "test/file.txt" in url
        assert "expires=" in url
        assert "signature=" in url

    async def test_get_url_with_download(self, backend):
        """Test URL generation with download flag."""
        await backend.put("test/document.pdf", b"pdf data", "application/pdf")

        url = await backend.get_url("test/document.pdf", download=True)

        assert "download=true" in url

    async def test_get_url_nonexistent(self, backend):
        """Test URL generation for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            await backend.get_url("nonexistent.txt")

    async def test_verify_url_valid(self, backend):
        """Test URL signature verification with valid signature."""
        await backend.put("test/file.txt", b"data", "text/plain")

        url = await backend.get_url("test/file.txt", expires_in=3600)

        # Extract query parameters
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Verify
        is_valid = backend.verify_url(
            key="test/file.txt",
            expires=params["expires"][0],
            signature=params["signature"][0],
            download=False,
        )

        assert is_valid is True

    async def test_verify_url_invalid_signature(self, backend):
        """Test URL verification with invalid signature."""
        await backend.put("test/file.txt", b"data", "text/plain")

        is_valid = backend.verify_url(
            key="test/file.txt",
            expires="9999999999",  # Future timestamp
            signature="invalid-signature",
            download=False,
        )

        assert is_valid is False

    async def test_verify_url_expired(self, backend):
        """Test URL verification with expired timestamp."""
        await backend.put("test/file.txt", b"data", "text/plain")

        # Use past timestamp
        is_valid = backend.verify_url(
            key="test/file.txt",
            expires="1000000000",  # Past timestamp (2001)
            signature="any-signature",
            download=False,
        )

        assert is_valid is False

    async def test_list_keys_empty(self, backend):
        """Test listing keys when storage is empty."""
        keys = await backend.list_keys()
        assert keys == []

    async def test_list_keys(self, backend):
        """Test listing all keys."""
        await backend.put("file1.txt", b"data1", "text/plain")
        await backend.put("file2.txt", b"data2", "text/plain")
        await backend.put("dir/file3.txt", b"data3", "text/plain")

        keys = await backend.list_keys()
        assert len(keys) == 3
        assert "file1.txt" in keys
        assert "file2.txt" in keys
        assert "dir/file3.txt" in keys

    async def test_list_keys_with_prefix(self, backend):
        """Test listing keys with prefix filter."""
        await backend.put("avatars/user1.jpg", b"img1", "image/jpeg")
        await backend.put("avatars/user2.jpg", b"img2", "image/jpeg")
        await backend.put("documents/doc1.pdf", b"pdf1", "application/pdf")

        keys = await backend.list_keys(prefix="avatars/")
        assert len(keys) == 2
        assert all(k.startswith("avatars/") for k in keys)

    async def test_list_keys_with_limit(self, backend):
        """Test listing keys with limit."""
        for i in range(10):
            await backend.put(f"file{i}.txt", b"data", "text/plain")

        keys = await backend.list_keys(limit=5)
        assert len(keys) == 5

    async def test_list_keys_excludes_metadata(self, backend):
        """Test that list_keys excludes .meta.json files."""
        await backend.put("file1.txt", b"data1", "text/plain")
        await backend.put("file2.txt", b"data2", "text/plain")

        keys = await backend.list_keys()

        # Should only include actual files, not .meta.json files
        assert len(keys) == 2
        assert all(not k.endswith(".meta.json") for k in keys)

    async def test_get_metadata(self, backend):
        """Test retrieving file metadata."""
        await backend.put(
            key="test/file.txt",
            data=b"test data",
            content_type="text/plain",
            metadata={"custom": "value"},
        )

        metadata = await backend.get_metadata("test/file.txt")
        assert metadata["size"] == 9
        assert metadata["content_type"] == "text/plain"
        assert metadata["custom"] == "value"
        assert "created_at" in metadata

    async def test_get_metadata_without_sidecar(self, backend):
        """Test getting metadata when sidecar file doesn't exist."""
        # Manually create file without metadata
        file_path = backend._get_file_path("test/file.txt")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"test data")

        metadata = await backend.get_metadata("test/file.txt")

        # Should return basic metadata from file stats
        assert metadata["size"] == 9
        assert metadata["content_type"] == "application/octet-stream"
        assert "created_at" in metadata

    async def test_get_metadata_nonexistent(self, backend):
        """Test getting metadata for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            await backend.get_metadata("nonexistent.txt")

    async def test_atomic_write(self, backend):
        """Test that writes are atomic (using temp file)."""
        # This is tested implicitly by put(), but we verify the temp file is cleaned up
        await backend.put("test/file.txt", b"data", "text/plain")

        file_path = backend._get_file_path("test/file.txt")
        temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")

        # Temp file should be gone
        assert not temp_path.exists()

        # Actual file should exist
        assert file_path.exists()

    async def test_invalid_key_validation(self, backend):
        """Test key validation."""
        # Empty key
        with pytest.raises(InvalidKeyError):
            await backend.put("", b"data", "text/plain")

        # Leading slash
        with pytest.raises(InvalidKeyError):
            await backend.put("/file.txt", b"data", "text/plain")

        # Path traversal
        with pytest.raises(InvalidKeyError):
            await backend.put("../etc/passwd", b"data", "text/plain")

        # Too long
        with pytest.raises(InvalidKeyError):
            await backend.put("x" * 1025, b"data", "text/plain")

    async def test_binary_data(self, backend):
        """Test storing binary data."""
        binary_data = bytes(range(256))

        await backend.put("binary.bin", binary_data, "application/octet-stream")

        retrieved = await backend.get("binary.bin")
        assert retrieved == binary_data

    async def test_railway_volume_detection(self, temp_dir, monkeypatch):
        """Test Railway volume path detection."""

        monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", temp_dir)

        # Create backend without explicit base_path
        from svc_infra.storage.settings import StorageSettings

        settings = StorageSettings()
        backend_type = settings.detect_backend()

        # Should detect local backend due to Railway env var
        assert backend_type == "local"

    async def test_special_characters_in_filename(self, backend):
        """Test handling special characters in filenames."""
        # Valid special characters
        await backend.put("file-name_v1.0.txt", b"data", "text/plain")
        assert await backend.exists("file-name_v1.0.txt")

        # Path with valid characters
        await backend.put("path/to/file_v2.txt", b"data", "text/plain")
        assert await backend.exists("path/to/file_v2.txt")
