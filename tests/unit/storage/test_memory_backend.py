"""Unit tests for MemoryBackend."""

import pytest

from svc_infra.storage.backends.memory import MemoryBackend
from svc_infra.storage.base import (
    FileNotFoundError,
    InvalidKeyError,
    QuotaExceededError,
)


@pytest.mark.storage
@pytest.mark.asyncio
class TestMemoryBackend:
    """Test suite for MemoryBackend."""

    async def test_put_and_get(self):
        """Test basic file storage and retrieval."""
        backend = MemoryBackend()

        # Put file
        url = await backend.put(
            key="test/file.txt",
            data=b"Hello, World!",
            content_type="text/plain",
        )

        assert url == "memory://test/file.txt"

        # Get file
        data = await backend.get("test/file.txt")
        assert data == b"Hello, World!"

    async def test_put_with_metadata(self):
        """Test storing file with custom metadata."""
        backend = MemoryBackend()

        await backend.put(
            key="test/file.txt",
            data=b"test data",
            content_type="text/plain",
            metadata={"user_id": "user_123", "tenant_id": "tenant_456"},
        )

        metadata = await backend.get_metadata("test/file.txt")
        assert metadata["user_id"] == "user_123"
        assert metadata["tenant_id"] == "tenant_456"
        assert metadata["size"] == 9
        assert metadata["content_type"] == "text/plain"
        assert "created_at" in metadata

    async def test_get_nonexistent_file(self):
        """Test getting a file that doesn't exist."""
        backend = MemoryBackend()

        with pytest.raises(FileNotFoundError) as exc_info:
            await backend.get("nonexistent.txt")

        assert "not found" in str(exc_info.value).lower()

    async def test_delete(self):
        """Test file deletion."""
        backend = MemoryBackend()

        # Put file
        await backend.put("test/file.txt", b"data", "text/plain")

        # Verify exists
        assert await backend.exists("test/file.txt")

        # Delete
        deleted = await backend.delete("test/file.txt")
        assert deleted is True

        # Verify doesn't exist
        assert not await backend.exists("test/file.txt")

    async def test_delete_nonexistent(self):
        """Test deleting a file that doesn't exist."""
        backend = MemoryBackend()

        deleted = await backend.delete("nonexistent.txt")
        assert deleted is False

    async def test_exists(self):
        """Test file existence check."""
        backend = MemoryBackend()

        # File doesn't exist initially
        assert not await backend.exists("test/file.txt")

        # Put file
        await backend.put("test/file.txt", b"data", "text/plain")

        # Now it exists
        assert await backend.exists("test/file.txt")

    async def test_get_url(self):
        """Test URL generation."""
        backend = MemoryBackend()

        await backend.put("test/file.txt", b"data", "text/plain")

        # Regular URL
        url = await backend.get_url("test/file.txt")
        assert url == "memory://test/file.txt"

        # Download URL
        url = await backend.get_url("test/file.txt", download=True)
        assert url == "memory://test/file.txt?download=true"

    async def test_get_url_nonexistent(self):
        """Test URL generation for nonexistent file."""
        backend = MemoryBackend()

        with pytest.raises(FileNotFoundError):
            await backend.get_url("nonexistent.txt")

    async def test_list_keys_empty(self):
        """Test listing keys when storage is empty."""
        backend = MemoryBackend()

        keys = await backend.list_keys()
        assert keys == []

    async def test_list_keys(self):
        """Test listing all keys."""
        backend = MemoryBackend()

        # Add multiple files
        await backend.put("file1.txt", b"data1", "text/plain")
        await backend.put("file2.txt", b"data2", "text/plain")
        await backend.put("dir/file3.txt", b"data3", "text/plain")

        keys = await backend.list_keys()
        assert len(keys) == 3
        assert "file1.txt" in keys
        assert "file2.txt" in keys
        assert "dir/file3.txt" in keys

    async def test_list_keys_with_prefix(self):
        """Test listing keys with prefix filter."""
        backend = MemoryBackend()

        await backend.put("avatars/user1.jpg", b"img1", "image/jpeg")
        await backend.put("avatars/user2.jpg", b"img2", "image/jpeg")
        await backend.put("documents/doc1.pdf", b"pdf1", "application/pdf")

        keys = await backend.list_keys(prefix="avatars/")
        assert len(keys) == 2
        assert "avatars/user1.jpg" in keys
        assert "avatars/user2.jpg" in keys
        assert "documents/doc1.pdf" not in keys

    async def test_list_keys_with_limit(self):
        """Test listing keys with limit."""
        backend = MemoryBackend()

        for i in range(10):
            await backend.put(f"file{i}.txt", b"data", "text/plain")

        keys = await backend.list_keys(limit=5)
        assert len(keys) == 5

    async def test_get_metadata(self):
        """Test retrieving file metadata."""
        backend = MemoryBackend()

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

    async def test_get_metadata_nonexistent(self):
        """Test getting metadata for nonexistent file."""
        backend = MemoryBackend()

        with pytest.raises(FileNotFoundError):
            await backend.get_metadata("nonexistent.txt")

    async def test_quota_enforcement(self):
        """Test storage quota enforcement."""
        backend = MemoryBackend(max_size=100)  # 100 bytes max

        # Put 50 bytes - should succeed
        await backend.put("file1.txt", b"x" * 50, "text/plain")

        # Put another 50 bytes - should succeed
        await backend.put("file2.txt", b"y" * 50, "text/plain")

        # Try to put 1 more byte - should fail
        with pytest.raises(QuotaExceededError) as exc_info:
            await backend.put("file3.txt", b"z", "text/plain")

        assert "quota exceeded" in str(exc_info.value).lower()

    async def test_quota_replace_file(self):
        """Test quota when replacing existing file."""
        backend = MemoryBackend(max_size=100)

        # Put 80 bytes
        await backend.put("file.txt", b"x" * 80, "text/plain")

        # Replace with 90 bytes - should succeed (only net +10 bytes)
        await backend.put("file.txt", b"y" * 90, "text/plain")

        data = await backend.get("file.txt")
        assert data == b"y" * 90

    async def test_invalid_key_empty(self):
        """Test validation for empty key."""
        backend = MemoryBackend()

        with pytest.raises(InvalidKeyError):
            await backend.put("", b"data", "text/plain")

    async def test_invalid_key_leading_slash(self):
        """Test validation for key with leading slash."""
        backend = MemoryBackend()

        with pytest.raises(InvalidKeyError):
            await backend.put("/file.txt", b"data", "text/plain")

    async def test_invalid_key_path_traversal(self):
        """Test validation for path traversal."""
        backend = MemoryBackend()

        with pytest.raises(InvalidKeyError):
            await backend.put("../etc/passwd", b"data", "text/plain")

        with pytest.raises(InvalidKeyError):
            await backend.put("dir/../other/file.txt", b"data", "text/plain")

    async def test_invalid_key_too_long(self):
        """Test validation for excessively long key."""
        backend = MemoryBackend()

        long_key = "x" * 1025  # Over 1024 limit

        with pytest.raises(InvalidKeyError):
            await backend.put(long_key, b"data", "text/plain")

    async def test_invalid_key_unsafe_chars(self):
        """Test validation for unsafe characters."""
        backend = MemoryBackend()

        with pytest.raises(InvalidKeyError):
            await backend.put("file<script>.txt", b"data", "text/plain")

        with pytest.raises(InvalidKeyError):
            await backend.put("file|dangerous.txt", b"data", "text/plain")

    async def test_clear(self):
        """Test clearing all storage."""
        backend = MemoryBackend()

        # Add files
        await backend.put("file1.txt", b"data1", "text/plain")
        await backend.put("file2.txt", b"data2", "text/plain")

        # Verify they exist
        assert await backend.exists("file1.txt")
        assert await backend.exists("file2.txt")

        # Clear
        await backend.clear()

        # Verify they're gone
        assert not await backend.exists("file1.txt")
        assert not await backend.exists("file2.txt")

    async def test_get_stats(self):
        """Test getting storage statistics."""
        backend = MemoryBackend(max_size=1000)

        stats = backend.get_stats()
        assert stats["file_count"] == 0
        assert stats["total_size"] == 0
        assert stats["max_size"] == 1000

        # Add files
        await backend.put("file1.txt", b"x" * 100, "text/plain")
        await backend.put("file2.txt", b"y" * 200, "text/plain")

        stats = backend.get_stats()
        assert stats["file_count"] == 2
        assert stats["total_size"] == 300
        assert stats["max_size"] == 1000

    async def test_concurrent_access(self):
        """Test thread-safe concurrent access."""
        import asyncio

        backend = MemoryBackend()

        async def put_file(n: int):
            await backend.put(f"file{n}.txt", f"data{n}".encode(), "text/plain")

        # Put 10 files concurrently
        await asyncio.gather(*[put_file(i) for i in range(10)])

        # Verify all files exist
        keys = await backend.list_keys()
        assert len(keys) == 10

    async def test_binary_data(self):
        """Test storing binary data."""
        backend = MemoryBackend()

        # Binary data (not UTF-8 text)
        binary_data = bytes(range(256))

        await backend.put("binary.bin", binary_data, "application/octet-stream")

        retrieved = await backend.get("binary.bin")
        assert retrieved == binary_data

    async def test_large_file(self):
        """Test storing larger file."""
        backend = MemoryBackend(max_size=10_000_000)  # 10MB

        # 1MB file
        large_data = b"x" * (1024 * 1024)

        await backend.put("large.bin", large_data, "application/octet-stream")

        retrieved = await backend.get("large.bin")
        assert len(retrieved) == 1024 * 1024
        assert retrieved == large_data
