"""Tests for document storage operations."""

import pytest

from svc_infra.documents.storage import (
    clear_storage,
    delete_document,
    download_document,
    get_document,
    list_documents,
    upload_document,
)
from svc_infra.storage.backends.memory import MemoryBackend


@pytest.fixture
def storage():
    """Create memory storage backend for testing."""
    return MemoryBackend()


@pytest.fixture(autouse=True)
def clear_metadata():
    """Clear document metadata before each test."""
    clear_storage()
    yield
    clear_storage()


@pytest.mark.asyncio
@pytest.mark.documents
class TestUploadDocument:
    """Tests for upload_document function."""

    async def test_upload_basic(self, storage):
        """Test basic document upload."""
        doc = await upload_document(
            storage=storage,
            user_id="user_123",
            file=b"test content",
            filename="test.pdf",
        )

        assert doc.id.startswith("doc_")
        assert doc.user_id == "user_123"
        assert doc.filename == "test.pdf"
        assert doc.file_size == 12
        assert doc.content_type == "application/pdf"
        assert doc.checksum.startswith("sha256:")
        assert doc.storage_path.startswith("documents/user_123/")

    async def test_upload_with_metadata(self, storage):
        """Test upload with custom metadata."""
        metadata = {"category": "legal", "year": 2024, "tags": ["important"]}

        doc = await upload_document(
            storage=storage,
            user_id="user_123",
            file=b"test content",
            filename="contract.pdf",
            metadata=metadata,
        )

        assert doc.metadata == metadata
        assert doc.metadata["category"] == "legal"
        assert doc.metadata["year"] == 2024

    async def test_upload_generates_unique_ids(self, storage):
        """Test that each upload generates unique document ID."""
        doc1 = await upload_document(
            storage=storage,
            user_id="user_123",
            file=b"content1",
            filename="file1.pdf",
        )
        doc2 = await upload_document(
            storage=storage,
            user_id="user_123",
            file=b"content2",
            filename="file2.pdf",
        )

        assert doc1.id != doc2.id
        assert doc1.storage_path != doc2.storage_path

    async def test_upload_stores_in_storage_backend(self, storage):
        """Test that file is actually stored in storage backend."""
        content = b"test file content"

        doc = await upload_document(
            storage=storage,
            user_id="user_123",
            file=content,
            filename="test.pdf",
        )

        # Verify file exists in storage
        retrieved_content = await storage.get(doc.storage_path)
        assert retrieved_content == content


@pytest.mark.asyncio
@pytest.mark.documents
class TestGetDocument:
    """Tests for get_document function."""

    async def test_get_existing_document(self, storage):
        """Test retrieving existing document."""
        doc = await upload_document(
            storage=storage,
            user_id="user_123",
            file=b"test",
            filename="test.pdf",
        )

        retrieved = get_document(doc.id)
        assert retrieved is not None
        assert retrieved.id == doc.id
        assert retrieved.filename == doc.filename

    def test_get_nonexistent_document(self, storage):
        """Test retrieving nonexistent document returns None."""
        result = get_document("nonexistent_id")
        assert result is None


@pytest.mark.asyncio
@pytest.mark.documents
class TestDownloadDocument:
    """Tests for download_document function."""

    async def test_download_existing_document(self, storage):
        """Test downloading existing document."""
        content = b"test file content to download"

        doc = await upload_document(
            storage=storage,
            user_id="user_123",
            file=content,
            filename="test.pdf",
        )

        downloaded = await download_document(storage, doc.id)
        assert downloaded == content

    async def test_download_nonexistent_document(self, storage):
        """Test downloading nonexistent document raises error."""
        with pytest.raises(ValueError, match="Document not found"):
            await download_document(storage, "nonexistent_id")


@pytest.mark.asyncio
@pytest.mark.documents
class TestDeleteDocument:
    """Tests for delete_document function."""

    async def test_delete_existing_document(self, storage):
        """Test deleting existing document."""
        doc = await upload_document(
            storage=storage,
            user_id="user_123",
            file=b"test",
            filename="test.pdf",
        )

        # Verify document exists
        assert get_document(doc.id) is not None
        assert await storage.exists(doc.storage_path)

        # Delete document
        success = await delete_document(storage, doc.id)
        assert success is True

        # Verify document is deleted
        assert get_document(doc.id) is None
        assert not await storage.exists(doc.storage_path)

    async def test_delete_nonexistent_document(self, storage):
        """Test deleting nonexistent document returns False."""
        success = await delete_document(storage, "nonexistent_id")
        assert success is False


@pytest.mark.asyncio
@pytest.mark.documents
class TestListDocuments:
    """Tests for list_documents function."""

    def test_list_empty(self, storage):
        """Test listing documents for user with no documents."""
        docs = list_documents("user_123")
        assert docs == []

    async def test_list_user_documents(self, storage):
        """Test listing documents for specific user."""
        # Upload documents for user_123
        doc1 = await upload_document(
            storage=storage, user_id="user_123", file=b"test1", filename="file1.pdf"
        )
        doc2 = await upload_document(
            storage=storage, user_id="user_123", file=b"test2", filename="file2.pdf"
        )

        # Upload document for different user
        await upload_document(
            storage=storage, user_id="user_456", file=b"test3", filename="file3.pdf"
        )

        # List documents for user_123
        docs = list_documents("user_123")
        assert len(docs) == 2
        doc_ids = {doc.id for doc in docs}
        assert doc1.id in doc_ids
        assert doc2.id in doc_ids

    async def test_list_pagination(self, storage):
        """Test pagination of document listing."""
        # Upload 5 documents
        for i in range(5):
            await upload_document(
                storage=storage,
                user_id="user_123",
                file=f"test{i}".encode(),
                filename=f"file{i}.pdf",
            )

        # Get first page (limit 2)
        page1 = list_documents("user_123", limit=2, offset=0)
        assert len(page1) == 2

        # Get second page
        page2 = list_documents("user_123", limit=2, offset=2)
        assert len(page2) == 2

        # Get third page
        page3 = list_documents("user_123", limit=2, offset=4)
        assert len(page3) == 1

        # Verify no overlap
        all_ids = {doc.id for doc in page1 + page2 + page3}
        assert len(all_ids) == 5

    async def test_list_user_isolation(self, storage):
        """Test that users can only see their own documents."""
        # User 1 uploads documents
        await upload_document(
            storage=storage, user_id="user_1", file=b"test1", filename="file1.pdf"
        )
        await upload_document(
            storage=storage, user_id="user_1", file=b"test2", filename="file2.pdf"
        )

        # User 2 uploads documents
        await upload_document(
            storage=storage, user_id="user_2", file=b"test3", filename="file3.pdf"
        )

        # Each user should only see their own documents
        user1_docs = list_documents("user_1")
        user2_docs = list_documents("user_2")

        assert len(user1_docs) == 2
        assert len(user2_docs) == 1
        assert all(doc.user_id == "user_1" for doc in user1_docs)
        assert all(doc.user_id == "user_2" for doc in user2_docs)
