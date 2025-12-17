"""
Tests for NoSQL service functionality.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from svc_infra.db.nosql.repository import NoSqlRepository
from svc_infra.db.nosql.service import NoSqlService


class TestNoSqlService:
    """Test NoSQL service functionality."""

    @pytest.fixture
    def nosql_service(self, mock_mongo_collection):
        """Create a NoSQL service instance for testing."""
        repo = NoSqlRepository(collection_name="test_collection")
        return NoSqlService(repo=repo)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database for testing."""
        db = Mock()
        db.test_collection = Mock()
        return db

    @pytest.mark.asyncio
    async def test_create_success(self, nosql_service, mock_db, sample_user_document_data):
        """Test successful document creation."""
        # Mock the repository create method
        expected_result = {**sample_user_document_data, "id": "user_123"}
        nosql_service.repo.create = AsyncMock(return_value=expected_result)

        result = await nosql_service.create(mock_db, sample_user_document_data)

        assert result == expected_result
        nosql_service.repo.create.assert_called_once_with(mock_db, sample_user_document_data)

    @pytest.mark.asyncio
    async def test_create_with_exception(self, nosql_service, mock_db, sample_user_document_data):
        """Test document creation with exception."""
        # Mock the repository create method to raise an exception
        nosql_service.repo.create = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(Exception):
            await nosql_service.create(mock_db, sample_user_document_data)

        nosql_service.repo.create.assert_called_once_with(mock_db, sample_user_document_data)

    @pytest.mark.asyncio
    async def test_get_success(self, nosql_service, mock_db, sample_user_document_data):
        """Test successful document retrieval by ID."""
        # Mock the repository get method
        nosql_service.repo.get = AsyncMock(return_value=sample_user_document_data)

        result = await nosql_service.get(mock_db, "user_123")

        assert result == sample_user_document_data
        nosql_service.repo.get.assert_called_once_with(mock_db, "user_123")

    @pytest.mark.asyncio
    async def test_get_not_found(self, nosql_service, mock_db):
        """Test document retrieval when document doesn't exist."""
        # Mock the repository get method to return None
        nosql_service.repo.get = AsyncMock(return_value=None)

        result = await nosql_service.get(mock_db, "nonexistent_id")

        assert result is None
        nosql_service.repo.get.assert_called_once_with(mock_db, "nonexistent_id")

    @pytest.mark.asyncio
    async def test_list_success(self, nosql_service, mock_db, sample_user_documents):
        """Test successful document listing."""
        # Convert documents to dictionaries
        documents_data = [doc.to_dict() for doc in sample_user_documents]

        # Mock the repository list method
        nosql_service.repo.list = AsyncMock(return_value=documents_data)

        result = await nosql_service.list(mock_db, limit=10, offset=0)

        assert len(result) == 3
        assert result[0]["email"] == "user1@example.com"
        assert result[1]["email"] == "user2@example.com"
        assert result[2]["email"] == "user3@example.com"

        nosql_service.repo.list.assert_called_once_with(mock_db, limit=10, offset=0, sort=None)

    @pytest.mark.asyncio
    async def test_list_with_sort(self, nosql_service, mock_db, sample_user_documents):
        """Test document listing with sorting."""
        # Convert documents to dictionaries
        documents_data = [doc.to_dict() for doc in sample_user_documents]

        # Mock the repository list method
        nosql_service.repo.list = AsyncMock(return_value=documents_data)

        sort = [("email", 1)]
        result = await nosql_service.list(mock_db, limit=10, offset=0, sort=sort)

        assert len(result) == 3
        nosql_service.repo.list.assert_called_once_with(mock_db, limit=10, offset=0, sort=sort)

    @pytest.mark.asyncio
    async def test_update_success(self, nosql_service, mock_db, sample_user_document_data):
        """Test successful document update."""
        # Mock the repository update method
        updated_data = {**sample_user_document_data, "name": "Updated Name"}
        nosql_service.repo.update = AsyncMock(return_value=updated_data)

        update_data = {"name": "Updated Name"}
        result = await nosql_service.update(mock_db, "user_123", update_data)

        assert result == updated_data
        nosql_service.repo.update.assert_called_once_with(mock_db, "user_123", update_data)

    @pytest.mark.asyncio
    async def test_update_not_found(self, nosql_service, mock_db):
        """Test document update when document doesn't exist."""
        # Mock the repository update method to return None
        nosql_service.repo.update = AsyncMock(return_value=None)

        update_data = {"name": "Updated Name"}
        result = await nosql_service.update(mock_db, "nonexistent_id", update_data)

        assert result is None
        nosql_service.repo.update.assert_called_once_with(mock_db, "nonexistent_id", update_data)

    @pytest.mark.asyncio
    async def test_delete_success(self, nosql_service, mock_db):
        """Test successful document deletion."""
        # Mock the repository delete method
        nosql_service.repo.delete = AsyncMock(return_value=True)

        result = await nosql_service.delete(mock_db, "user_123")

        assert result is True
        nosql_service.repo.delete.assert_called_once_with(mock_db, "user_123")

    @pytest.mark.asyncio
    async def test_delete_not_found(self, nosql_service, mock_db):
        """Test document deletion when document doesn't exist."""
        # Mock the repository delete method to return False
        nosql_service.repo.delete = AsyncMock(return_value=False)

        result = await nosql_service.delete(mock_db, "nonexistent_id")

        assert result is False
        nosql_service.repo.delete.assert_called_once_with(mock_db, "nonexistent_id")

    @pytest.mark.asyncio
    async def test_exists_true(self, nosql_service, mock_db):
        """Test document existence check when document exists."""
        # Mock the repository exists method
        nosql_service.repo.exists = AsyncMock(return_value=True)

        result = await nosql_service.exists(mock_db, where=[{"email": "test@example.com"}])

        assert result is True
        nosql_service.repo.exists.assert_called_once_with(
            mock_db, where=[{"email": "test@example.com"}]
        )

    @pytest.mark.asyncio
    async def test_exists_false(self, nosql_service, mock_db):
        """Test document existence check when document doesn't exist."""
        # Mock the repository exists method
        nosql_service.repo.exists = AsyncMock(return_value=False)

        result = await nosql_service.exists(mock_db, where=[{"email": "nonexistent@example.com"}])

        assert result is False
        nosql_service.repo.exists.assert_called_once_with(
            mock_db, where=[{"email": "nonexistent@example.com"}]
        )

    @pytest.mark.asyncio
    async def test_count_success(self, nosql_service, mock_db):
        """Test document counting."""
        # Mock the repository count method
        nosql_service.repo.count = AsyncMock(return_value=5)

        result = await nosql_service.count(mock_db)

        assert result == 5
        nosql_service.repo.count.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_search_success(self, nosql_service, mock_db, sample_user_documents):
        """Test document search functionality."""
        # Convert documents to dictionaries
        documents_data = [doc.to_dict() for doc in sample_user_documents]

        # Mock the repository search method
        nosql_service.repo.search = AsyncMock(return_value=documents_data)

        result = await nosql_service.search(
            mock_db, q="test", fields=["email", "name"], limit=10, offset=0
        )

        assert len(result) == 3
        nosql_service.repo.search.assert_called_once_with(
            mock_db, q="test", fields=["email", "name"], limit=10, offset=0, sort=None
        )

    @pytest.mark.asyncio
    async def test_count_filtered_success(self, nosql_service, mock_db):
        """Test filtered document counting."""
        # Mock the repository count_filtered method
        nosql_service.repo.count_filtered = AsyncMock(return_value=3)

        result = await nosql_service.count_filtered(mock_db, q="test", fields=["email", "name"])

        assert result == 3
        nosql_service.repo.count_filtered.assert_called_once_with(
            mock_db, q="test", fields=["email", "name"]
        )

    @pytest.mark.asyncio
    async def test_pre_create_hook(self, nosql_service, mock_db, sample_user_document_data):
        """Test pre-create hook functionality."""
        # Override the pre_create method to add a timestamp
        original_pre_create = nosql_service.pre_create

        async def custom_pre_create(data):
            data["created_by"] = "test_user"
            return data

        nosql_service.pre_create = custom_pre_create
        try:
            # Mock the repository create method
            expected_result = {**sample_user_document_data, "created_by": "test_user"}
            nosql_service.repo.create = AsyncMock(return_value=expected_result)

            result = await nosql_service.create(mock_db, sample_user_document_data)

            assert result == expected_result
            # Verify the pre_create hook was called
            assert "created_by" in result
        finally:
            nosql_service.pre_create = original_pre_create

    @pytest.mark.asyncio
    async def test_pre_update_hook(self, nosql_service, mock_db, sample_user_document_data):
        """Test pre-update hook functionality."""
        # Override the pre_update method to add a timestamp
        original_pre_update = nosql_service.pre_update

        async def custom_pre_update(data):
            data["updated_by"] = "test_user"
            return data

        nosql_service.pre_update = custom_pre_update
        try:
            # Mock the repository update method
            expected_result = {**sample_user_document_data, "updated_by": "test_user"}
            nosql_service.repo.update = AsyncMock(return_value=expected_result)

            update_data = {"name": "Updated Name"}
            result = await nosql_service.update(mock_db, "user_123", update_data)

            assert result == expected_result
            # Verify the pre_update hook was called
            assert "updated_by" in result
        finally:
            nosql_service.pre_update = original_pre_update
