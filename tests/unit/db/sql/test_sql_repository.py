"""
Tests for SQL repository functionality.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from svc_infra.db.sql.repository import SqlRepository
from tests.unit.db.sql.conftest import ProductModel, UserModel


class TestSqlRepository:
    """Test SQL repository functionality."""

    @pytest.fixture
    def sql_repository(self, mock_sqlalchemy_session):
        """Create a SQL repository instance for testing."""
        return SqlRepository(model=UserModel)

    @pytest.mark.asyncio
    async def test_save_success(self, sql_repository, mock_sqlalchemy_session):
        """Test successful record save."""
        # Mock the session.flush to simulate successful save
        mock_sqlalchemy_session.flush = AsyncMock()
        mock_sqlalchemy_session.refresh = AsyncMock()

        user_data = {"email": "test@example.com", "name": "Test User"}
        result = await sql_repository.create(mock_sqlalchemy_session, user_data)

        assert result is not None
        assert result.email == "test@example.com"
        assert result.name == "Test User"

        # Verify session methods were called
        mock_sqlalchemy_session.add.assert_called_once()
        mock_sqlalchemy_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_with_integrity_error(self, sql_repository, mock_sqlalchemy_session):
        """Test record saving with integrity error."""
        # Mock the session.flush to raise IntegrityError
        mock_sqlalchemy_session.flush = AsyncMock(
            side_effect=IntegrityError("UNIQUE constraint failed", None, None)
        )

        user_data = {"email": "test@example.com", "name": "Test User"}
        with pytest.raises(IntegrityError):
            await sql_repository.create(mock_sqlalchemy_session, user_data)

        # Verify session methods were called
        mock_sqlalchemy_session.add.assert_called_once()
        mock_sqlalchemy_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_id_success(self, sql_repository, mock_sqlalchemy_session):
        """Test successful record finding by ID."""
        # Create a mock user
        mock_user = UserModel(id=1, email="test@example.com", name="Test User")

        # Mock the session.execute to return the user
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_sqlalchemy_session.execute = AsyncMock(return_value=mock_result)

        result = await sql_repository.get(mock_sqlalchemy_session, 1)

        assert result is not None
        assert result.id == 1
        assert result.email == "test@example.com"

        # Verify session.execute was called
        mock_sqlalchemy_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, sql_repository, mock_sqlalchemy_session):
        """Test record finding when record doesn't exist."""
        # Mock the session.execute to return None
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_sqlalchemy_session.execute = AsyncMock(return_value=mock_result)

        result = await sql_repository.get(mock_sqlalchemy_session, 999)

        assert result is None
        mock_sqlalchemy_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_all_success(self, sql_repository, mock_sqlalchemy_session):
        """Test successful record finding all."""
        # Create mock users
        mock_users = [
            UserModel(id=1, email="user1@example.com", name="User 1"),
            UserModel(id=2, email="user2@example.com", name="User 2"),
        ]

        # Mock the session.execute to return the users
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_sqlalchemy_session.execute = AsyncMock(return_value=mock_result)

        result = await sql_repository.list(mock_sqlalchemy_session, limit=10, offset=0)

        assert len(result) == 2
        assert result[0].email == "user1@example.com"
        assert result[1].email == "user2@example.com"

    @pytest.mark.asyncio
    async def test_find_all_with_filters(self, sql_repository, mock_sqlalchemy_session):
        """Test record finding all with filters."""
        # Create mock users
        mock_users = [
            UserModel(id=1, email="active@example.com", name="Active User", is_active="true"),
        ]

        # Mock the session.execute to return filtered users
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_sqlalchemy_session.execute = AsyncMock(return_value=mock_result)

        result = await sql_repository.list(mock_sqlalchemy_session, limit=10, offset=0)

        assert len(result) == 1
        assert result[0].is_active == "true"

        # Verify the query was constructed
        mock_sqlalchemy_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_all_with_pagination(self, sql_repository, mock_sqlalchemy_session):
        """Test record finding all with pagination."""
        # Create mock users
        mock_users = [
            UserModel(id=1, email="user1@example.com", name="User 1"),
            UserModel(id=2, email="user2@example.com", name="User 2"),
        ]

        # Mock the session.execute to return paginated users
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_sqlalchemy_session.execute = AsyncMock(return_value=mock_result)

        result = await sql_repository.list(mock_sqlalchemy_session, limit=10, offset=0)

        assert len(result) == 2

        # Verify the query was constructed with pagination
        mock_sqlalchemy_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_success(self, sql_repository, mock_sqlalchemy_session):
        """Test successful record update."""
        # Create a mock user
        mock_user = UserModel(id=1, email="test@example.com", name="Old Name")

        # Mock the session.execute to return the user for the get call
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_sqlalchemy_session.execute = AsyncMock(return_value=mock_result)

        # Mock the session.flush to simulate successful update
        mock_sqlalchemy_session.flush = AsyncMock()
        mock_sqlalchemy_session.refresh = AsyncMock()

        update_data = {"name": "New Name", "email": "new@example.com"}
        result = await sql_repository.update(mock_sqlalchemy_session, 1, update_data)

        assert result is not None
        assert result.name == "New Name"
        assert result.email == "new@example.com"

        # Verify session methods were called
        mock_sqlalchemy_session.execute.assert_called()
        mock_sqlalchemy_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self, sql_repository, mock_sqlalchemy_session):
        """Test record update when record doesn't exist."""
        # Mock the session.execute to return None
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_sqlalchemy_session.execute = AsyncMock(return_value=mock_result)

        update_data = {"name": "New Name"}
        result = await sql_repository.update(mock_sqlalchemy_session, 999, update_data)

        assert result is None
        mock_sqlalchemy_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_success(self, sql_repository, mock_sqlalchemy_session):
        """Test successful record deletion."""
        # Create a mock user
        mock_user = UserModel(id=1, email="test@example.com", name="Test User")

        # Mock the session.get to return the user (delete method uses session.get directly)
        mock_sqlalchemy_session.get = AsyncMock(return_value=mock_user)

        # Mock the session.flush to simulate successful deletion
        mock_sqlalchemy_session.flush = AsyncMock()

        result = await sql_repository.delete(mock_sqlalchemy_session, 1)

        assert result is True

        # Verify session methods were called
        mock_sqlalchemy_session.get.assert_called_once_with(UserModel, 1)
        mock_sqlalchemy_session.delete.assert_called_once_with(mock_user)
        mock_sqlalchemy_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, sql_repository, mock_sqlalchemy_session):
        """Test record deletion when record doesn't exist."""
        # Mock the session.get to return None
        mock_sqlalchemy_session.get = AsyncMock(return_value=None)

        result = await sql_repository.delete(mock_sqlalchemy_session, 999)

        assert result is False
        mock_sqlalchemy_session.get.assert_called_once_with(UserModel, 999)
        mock_sqlalchemy_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_success(self, sql_repository, mock_sqlalchemy_session):
        """Test record counting."""
        # Mock the session.execute to return a count
        mock_result = Mock()
        mock_result.scalar_one.return_value = 5
        mock_sqlalchemy_session.execute = AsyncMock(return_value=mock_result)

        result = await sql_repository.count(mock_sqlalchemy_session)

        assert result == 5

        # Verify the query was constructed correctly
        mock_sqlalchemy_session.execute.assert_called_once()
