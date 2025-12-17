"""
NoSQL database test fixtures and configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest

from tests.unit.utils.test_helpers import MockDatabaseSession


# Test NoSQL document models
class UserDocumentModel:
    """Test user document model."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.email = kwargs.get("email")
        self.name = kwargs.get("name")
        self.is_active = kwargs.get("is_active", True)
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        self.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserDocumentModel":
        """Create document from dictionary."""
        return cls(**data)


class ProductDocumentModel:
    """Test product document model."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.price = kwargs.get("price")
        self.category_id = kwargs.get("category_id")
        self.active = kwargs.get("active", True)
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        self.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "category_id": self.category_id,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductDocumentModel":
        """Create document from dictionary."""
        return cls(**data)


@pytest.fixture
def mock_mongo_client():
    """Create a mock MongoDB client for testing."""
    client = Mock()
    client.list_database_names = AsyncMock(return_value=["test_db"])
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_mongo_database():
    """Create a mock MongoDB database for testing."""
    db = Mock()
    db.list_collection_names = AsyncMock(return_value=["users", "products"])
    db.command = AsyncMock(return_value={"ok": 1})
    return db


@pytest.fixture
def mock_mongo_collection():
    """Create a mock MongoDB collection for testing."""
    collection = Mock()
    collection.insert_one = AsyncMock()
    collection.insert_many = AsyncMock()
    collection.find_one = AsyncMock()
    collection.find = AsyncMock()
    collection.update_one = AsyncMock()
    collection.update_many = AsyncMock()
    collection.delete_one = AsyncMock()
    collection.delete_many = AsyncMock()
    collection.count_documents = AsyncMock()
    collection.create_index = AsyncMock()
    collection.create_indexes = AsyncMock()
    collection.drop_index = AsyncMock()
    collection.drop_indexes = AsyncMock()
    return collection


@pytest.fixture
def mock_nosql_session():
    """Create a mock NoSQL database session."""
    return MockDatabaseSession()


@pytest.fixture
def test_user_document():
    """Provide the test user document model."""
    return UserDocumentModel


@pytest.fixture
def test_product_document():
    """Provide the test product document model."""
    return ProductDocumentModel


@pytest.fixture
def sample_user_document_data():
    """Provide sample user document data for testing."""
    return {
        "id": "user_123",
        "email": "test@example.com",
        "name": "Test User",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_product_document_data():
    """Provide sample product document data for testing."""
    return {
        "id": "product_456",
        "name": "Test Product",
        "description": "A test product for testing",
        "price": 1999,
        "category_id": "category_789",
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_user_documents():
    """Provide sample user documents for testing."""
    return [
        UserDocumentModel(
            id="user_1",
            email="user1@example.com",
            name="User 1",
            is_active=True,
        ),
        UserDocumentModel(
            id="user_2",
            email="user2@example.com",
            name="User 2",
            is_active=True,
        ),
        UserDocumentModel(
            id="user_3",
            email="user3@example.com",
            name="User 3",
            is_active=False,
        ),
    ]


@pytest.fixture
def sample_product_documents():
    """Provide sample product documents for testing."""
    return [
        ProductDocumentModel(
            id="product_1",
            name="Laptop",
            description="High-performance laptop",
            price=99999,
            category_id="electronics",
            active=True,
        ),
        ProductDocumentModel(
            id="product_2",
            name="Mouse",
            description="Wireless mouse",
            price=2999,
            category_id="electronics",
            active=True,
        ),
        ProductDocumentModel(
            id="product_3",
            name="Keyboard",
            description="Mechanical keyboard",
            price=7999,
            category_id="electronics",
            active=False,
        ),
    ]


@pytest.fixture(autouse=True)
def _nosql_env(monkeypatch):
    """Set up NoSQL database environment for testing."""
    # Mock MongoDB URL
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB", "test_db")

    # Mock additional NoSQL environment variables
    monkeypatch.setenv("MONGO_MAX_POOL_SIZE", "100")
    monkeypatch.setenv("MONGO_MIN_POOL_SIZE", "0")
    monkeypatch.setenv("MONGO_MAX_IDLE_TIME_MS", "30000")
    monkeypatch.setenv("MONGO_WAIT_QUEUE_TIMEOUT_MS", "5000")
    monkeypatch.setenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")
    monkeypatch.setenv("MONGO_SOCKET_TIMEOUT_MS", "20000")
    monkeypatch.setenv("MONGO_CONNECT_TIMEOUT_MS", "20000")
    monkeypatch.setenv("MONGO_HEARTBEAT_FREQUENCY_MS", "10000")
    monkeypatch.setenv("MONGO_LOCAL_THRESHOLD_MS", "15")
    monkeypatch.setenv("MONGO_RETRY_WRITES", "true")
    monkeypatch.setenv("MONGO_RETRY_READS", "true")


@pytest.fixture
def mock_index_models():
    """Provide mock index models for testing."""
    from unittest.mock import Mock

    indexes = [
        Mock(name="email_1", keys=[("email", 1)]),
        Mock(name="name_1", keys=[("name", 1)]),
        Mock(name="created_at_1", keys=[("created_at", -1)]),
    ]

    return indexes


@pytest.fixture
def mock_collection_info():
    """Provide mock collection information for testing."""
    return {
        "name": "test_collection",
        "type": "collection",
        "options": {},
        "info": {"readOnly": False, "uuid": "test-uuid-123"},
        "idIndex": {"v": 2, "key": {"_id": 1}, "name": "_id_"},
    }
