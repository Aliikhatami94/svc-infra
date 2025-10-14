"""
SQL database test fixtures and configuration.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from sqlalchemy import Column, DateTime, Integer, String, create_engine, func
from sqlalchemy.ext.declarative import declarative_base

# Test database models
from sqlalchemy.orm import declarative_base, sessionmaker

from tests.utils.test_helpers import MockDatabaseSession

Base = declarative_base()


class UserModel(Base):
    __tablename__ = "test_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    is_active = Column(String(10), default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProductModel(Base):
    __tablename__ = "test_products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    price = Column(Integer, nullable=False)  # Price in cents
    active = Column(String(10), default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


@pytest.fixture
def mock_sql_session():
    """Create a mock SQL database session."""
    return MockDatabaseSession()


@pytest.fixture
def test_user_model():
    """Provide the test user model."""
    return UserModel


@pytest.fixture
def test_product_model():
    """Provide the test product model."""
    return ProductModel


@pytest.fixture
def sample_user_data():
    """Provide sample user data for testing."""
    return {"email": "test@example.com", "name": "Test User", "is_active": "true"}


@pytest.fixture
def sample_product_data():
    """Provide sample product data for testing."""
    return {
        "name": "Test Product",
        "description": "A test product for testing",
        "price": 1999,  # $19.99 in cents
        "active": "true",
    }


@pytest.fixture
def mock_sqlalchemy_engine(mocker):
    """Mock SQLAlchemy engine."""
    engine = Mock()
    engine.execute = AsyncMock()
    engine.begin = Mock()
    engine.connect = Mock()
    return engine


@pytest.fixture
def mock_sqlalchemy_session(mocker):
    """Mock SQLAlchemy session."""
    session = Mock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.add = Mock()  # add is not async
    session.delete = Mock()  # delete is not async
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture(autouse=True)
def _sql_env(monkeypatch):
    """Set up SQL database environment for testing."""
    # Mock database URL
    monkeypatch.setenv("SQL_URL", "sqlite:///:memory:")

    # Mock additional database environment variables
    monkeypatch.setenv("SQL_ECHO", "false")
    monkeypatch.setenv("SQL_POOL_SIZE", "5")
    monkeypatch.setenv("SQL_MAX_OVERFLOW", "10")
    monkeypatch.setenv("SQL_POOL_TIMEOUT", "30")
    monkeypatch.setenv("SQL_POOL_RECYCLE", "3600")
