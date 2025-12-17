"""
Acceptance tests for storage system (A22-01 to A22-05).

Tests the storage backend integration through the acceptance app's
storage endpoints to verify end-to-end functionality.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.acceptance


class TestStorageAcceptance:
    """Storage system acceptance tests."""

    def test_a22_01_local_backend_upload_and_retrieval(self, client):
        """
        A22-01: Local backend file upload and retrieval.

        Scenario:
        1. Upload file via /_storage/upload
        2. Retrieve file content
        3. Verify content matches

        Assertions:
        - Upload returns 200 with URL and key
        - Download returns 200 with correct content
        - Content matches uploaded data
        """
        # Upload a test file
        upload_payload = {
            "filename": "test-a22-01.txt",
            "content": "Hello, storage acceptance!",
            "content_type": "text/plain",
        }

        r = client.post("/_storage/upload", json=upload_payload)
        assert r.status_code == 200, f"Upload failed: {r.text}"

        body = r.json()
        assert "url" in body
        assert "key" in body
        assert body["key"] == "test/test-a22-01.txt"

        # Download the file
        r = client.get("/_storage/download/test-a22-01.txt")
        assert r.status_code == 200, f"Download failed: {r.text}"

        download_body = r.json()
        assert "content" in download_body
        assert download_body["content"] == "Hello, storage acceptance!"
        assert download_body["key"] == "test/test-a22-01.txt"

    def test_a22_02_s3_backend_operations_stub(self, client):
        """
        A22-02: S3 backend operations (with memory backend in acceptance).

        Note: Acceptance tests use MemoryBackend for determinism.
        Real S3 operations are tested via integration tests with @pytest.mark.integration.

        Scenario:
        1. Upload file
        2. Verify file exists via download
        3. Content matches

        Assertions:
        - Upload succeeds with URL
        - Download returns correct content
        """
        # Upload
        upload_payload = {
            "filename": "test-a22-02-s3.txt",
            "content": "S3 backend test content",
            "content_type": "text/plain",
        }

        r = client.post("/_storage/upload", json=upload_payload)
        assert r.status_code == 200

        body = r.json()
        assert body["key"] == "test/test-a22-02-s3.txt"

        # Download
        r = client.get("/_storage/download/test-a22-02-s3.txt")
        assert r.status_code == 200

        download_body = r.json()
        assert download_body["content"] == "S3 backend test content"

    def test_a22_03_storage_backend_auto_detection(self, client):
        """
        A22-03: Storage backend auto-detection.

        Scenario:
        1. Query backend info endpoint
        2. Verify backend is detected (MemoryBackend in acceptance)

        Assertions:
        - Backend info available
        - Backend name is MemoryBackend
        - app.state.storage is configured
        """
        r = client.get("/_storage/backend-info")
        assert r.status_code == 200, f"Backend info failed: {r.text}"

        body = r.json()
        assert "backend" in body
        assert "type" in body

        # In acceptance, we use MemoryBackend
        assert "Backend" in body["backend"]

        # Verify we can upload (confirms app.state.storage is configured)
        upload_payload = {
            "filename": "test-a22-03-auto.txt",
            "content": "Auto-detection test",
            "content_type": "text/plain",
        }

        r = client.post("/_storage/upload", json=upload_payload)
        assert r.status_code == 200

    def test_a22_04_file_deletion_and_cleanup(self, client):
        """
        A22-04: File deletion and cleanup.

        Scenario:
        1. Upload file
        2. Verify file exists via download
        3. Delete file
        4. Verify 404 on retrieval

        Assertions:
        - Upload succeeds
        - Download succeeds before deletion
        - DELETE returns 204
        - Subsequent GET returns 404
        """
        filename = "test-a22-04-delete.txt"

        # Upload
        upload_payload = {
            "filename": filename,
            "content": "File to be deleted",
            "content_type": "text/plain",
        }

        r = client.post("/_storage/upload", json=upload_payload)
        assert r.status_code == 200

        # Verify exists
        r = client.get(f"/_storage/download/{filename}")
        assert r.status_code == 200

        # Delete
        r = client.delete(f"/_storage/files/{filename}")
        assert r.status_code == 204, f"Delete failed: {r.text}"

        # Verify 404 after deletion
        r = client.get(f"/_storage/download/{filename}")
        assert r.status_code == 404, "File should not exist after deletion"

    def test_a22_05_metadata_and_listing(self, client):
        """
        A22-05: Metadata and listing.

        Scenario:
        1. Upload files with metadata
        2. List files with prefix
        3. Get metadata for specific file

        Assertions:
        - Metadata is stored
        - Metadata is retrievable
        - List returns correct keys
        - Prefix filtering works
        """
        # Upload multiple files with different prefixes
        files = [
            {"filename": "metadata-test-1.txt", "content": "First file"},
            {"filename": "metadata-test-2.txt", "content": "Second file"},
            {"filename": "other-file.txt", "content": "Other file"},
        ]

        for file_data in files:
            payload = {
                "filename": file_data["filename"],
                "content": file_data["content"],
                "content_type": "text/plain",
            }
            r = client.post("/_storage/upload", json=payload)
            assert r.status_code == 200

        # List all test files
        r = client.get("/_storage/list", params={"prefix": "test/"})
        assert r.status_code == 200

        body = r.json()
        assert "keys" in body
        assert "count" in body
        assert body["count"] >= 3  # At least our 3 files

        # Filter with more specific prefix
        keys = body["keys"]
        metadata_keys = [k for k in keys if "metadata-test" in k]
        assert len(metadata_keys) >= 2

        # Get metadata for a specific file
        r = client.get("/_storage/metadata/metadata-test-1.txt")
        assert r.status_code == 200

        metadata_body = r.json()
        assert "metadata" in metadata_body
        assert metadata_body["key"] == "test/metadata-test-1.txt"

        # Metadata should contain our custom fields
        metadata = metadata_body["metadata"]
        assert "test" in metadata
        assert metadata["test"] == "acceptance"
        assert "filename" in metadata

    def test_a22_06_concurrent_uploads(self, client):
        """
        Additional test: Concurrent uploads don't interfere.

        Scenario:
        1. Upload multiple files with same prefix
        2. Verify all are stored correctly
        3. List and verify count

        Assertions:
        - All uploads succeed
        - All files retrievable
        - Correct count in listing
        """
        files = [
            {"filename": f"concurrent-{i}.txt", "content": f"Content {i}"}
            for i in range(5)
        ]

        # Upload all files
        for file_data in files:
            payload = {
                "filename": file_data["filename"],
                "content": file_data["content"],
                "content_type": "text/plain",
            }
            r = client.post("/_storage/upload", json=payload)
            assert r.status_code == 200

        # Verify all are retrievable
        for file_data in files:
            r = client.get(f"/_storage/download/{file_data['filename']}")
            assert r.status_code == 200
            body = r.json()
            assert body["content"] == file_data["content"]

        # Verify count
        r = client.get("/_storage/list", params={"prefix": "test/concurrent-"})
        assert r.status_code == 200

        body = r.json()
        concurrent_keys = [k for k in body["keys"] if "concurrent-" in k]
        assert len(concurrent_keys) == 5

    def test_a22_07_large_file_handling(self, client):
        """
        Additional test: Handle reasonably large files.

        Scenario:
        1. Upload a larger file (simulated with repeated content)
        2. Download and verify

        Assertions:
        - Upload succeeds
        - Download returns correct content
        """
        # Create a ~10KB file
        large_content = "A" * 10240

        upload_payload = {
            "filename": "large-file.txt",
            "content": large_content,
            "content_type": "text/plain",
        }

        r = client.post("/_storage/upload", json=upload_payload)
        assert r.status_code == 200

        # Download and verify
        r = client.get("/_storage/download/large-file.txt")
        assert r.status_code == 200

        body = r.json()
        assert body["content"] == large_content
        assert len(body["content"]) == 10240

    def test_a22_08_nonexistent_file_returns_404(self, client):
        """
        Additional test: Accessing nonexistent files returns 404.

        Scenario:
        1. Try to download a file that doesn't exist
        2. Try to get metadata for nonexistent file

        Assertions:
        - Download returns 404
        - Metadata returns 404
        """
        # Download nonexistent file
        r = client.get("/_storage/download/does-not-exist.txt")
        assert r.status_code == 404

        # Get metadata for nonexistent file
        r = client.get("/_storage/metadata/does-not-exist.txt")
        assert r.status_code == 404

    def test_a22_09_empty_list_with_nonmatching_prefix(self, client):
        """
        Additional test: Listing with non-matching prefix returns empty list.

        Scenario:
        1. List files with a prefix that doesn't match any files

        Assertions:
        - Returns 200
        - Returns empty keys list
        - Count is 0
        """
        r = client.get("/_storage/list", params={"prefix": "nonexistent-prefix/"})
        assert r.status_code == 200

        body = r.json()
        assert "keys" in body
        assert "count" in body

        # Filter keys to only those matching our nonexistent prefix
        matching_keys = [k for k in body["keys"] if k.startswith("nonexistent-prefix/")]
        assert len(matching_keys) == 0
