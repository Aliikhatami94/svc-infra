"""Tests for document management demo.

These tests demonstrate how to test document operations
using svc-infra's storage and document management.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from svc_infra_template.documents import router

from svc_infra.documents.storage import clear_storage
from svc_infra.storage import MemoryBackend


@pytest.fixture(autouse=True)
def clear_metadata():
    """Clear document metadata before each test for isolation."""
    clear_storage()
    yield
    clear_storage()


@pytest.fixture(scope="function")
def storage():
    """Create in-memory storage backend for each test."""
    return MemoryBackend()


@pytest.fixture
def app(storage):
    """Create FastAPI app with document routes and override storage dependency."""
    from svc_infra_template.documents.router import get_storage

    app = FastAPI()
    app.include_router(router)

    # Override storage dependency to use test storage
    app.dependency_overrides[get_storage] = lambda: storage

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def test_upload_document(client):
    """Test uploading a document with metadata."""
    response = client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "contract.pdf",
            "content": "test contract content",
            "category": "contract",
            "tags": ["vendor", "2024"],
            "department": "legal",
            "year": 2024,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["user_id"] == "user_123"
    assert data["filename"] == "contract.pdf"
    assert data["category"] == "contract"
    assert "vendor" in data["tags"]
    assert data["department"] == "legal"
    assert data["year"] == 2024


def test_list_documents(client):
    """Test listing documents with filters."""
    # Upload multiple documents
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "contract1.pdf",
            "content": "content1",
            "category": "contract",
            "tags": ["vendor"],
            "department": "legal",
        },
    )
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "invoice1.pdf",
            "content": "content2",
            "category": "invoice",
            "tags": ["payment"],
            "department": "finance",
        },
    )
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_456",
            "filename": "report1.pdf",
            "content": "content3",
            "category": "report",
        },
    )

    # List all documents for user_123
    response = client.get("/documents/list?user_id=user_123")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Filter by category
    response = client.get("/documents/list?user_id=user_123&category=contract")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "contract"

    # Filter by department
    response = client.get("/documents/list?user_id=user_123&department=legal")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["department"] == "legal"


def test_get_document(client):
    """Test getting document by ID."""
    # Upload document
    upload_response = client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "test.pdf",
            "content": "content",
            "category": "report",
        },
    )
    doc_id = upload_response.json()["id"]

    # Get document
    response = client.get(f"/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert data["filename"] == "test.pdf"


def test_get_document_not_found(client):
    """Test getting non-existent document."""
    response = client.get("/documents/nonexistent_id")
    assert response.status_code == 404


def test_download_document(client):
    """Test downloading document content."""
    # Upload document
    upload_response = client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "test.pdf",
            "content": "test content here",
            "category": "report",
        },
    )
    doc_id = upload_response.json()["id"]

    # Download document
    response = client.get(f"/documents/{doc_id}/download")
    assert response.status_code == 200
    assert b"test content here" in response.content
    assert "attachment" in response.headers["content-disposition"]
    assert "test.pdf" in response.headers["content-disposition"]


def test_delete_document(client):
    """Test deleting a document."""
    # Upload document
    upload_response = client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "test.pdf",
            "content": "content",
            "category": "report",
        },
    )
    doc_id = upload_response.json()["id"]

    # Delete document
    response = client.delete(f"/documents/{doc_id}")
    assert response.status_code == 204

    # Verify it's gone
    response = client.get(f"/documents/{doc_id}")
    assert response.status_code == 404


def test_delete_document_not_found(client):
    """Test deleting non-existent document."""
    response = client.delete("/documents/nonexistent_id")
    assert response.status_code == 404


def test_filter_by_tags(client):
    """Test filtering documents by tags."""
    # Upload documents with different tags
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "doc1.pdf",
            "content": "content1",
            "category": "contract",
            "tags": ["urgent", "vendor"],
        },
    )
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "doc2.pdf",
            "content": "content2",
            "category": "invoice",
            "tags": ["paid", "vendor"],
        },
    )
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "doc3.pdf",
            "content": "content3",
            "category": "report",
            "tags": ["monthly"],
        },
    )

    # Filter by vendor tag
    response = client.get("/documents/list?user_id=user_123&tags=vendor")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Filter by urgent tag
    response = client.get("/documents/list?user_id=user_123&tags=urgent")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "doc1.pdf"


def test_filter_by_year(client):
    """Test filtering documents by year."""
    # Upload documents with different years
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "2024_report.pdf",
            "content": "content1",
            "category": "report",
            "year": 2024,
        },
    )
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "2023_report.pdf",
            "content": "content2",
            "category": "report",
            "year": 2023,
        },
    )

    # Filter by 2024
    response = client.get("/documents/list?user_id=user_123&year=2024")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["year"] == 2024


def test_filter_by_project(client):
    """Test filtering documents by project."""
    # Upload documents with different projects
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "doc1.pdf",
            "content": "content1",
            "category": "report",
            "project": "alpha",
        },
    )
    client.post(
        "/documents/upload",
        json={
            "user_id": "user_123",
            "filename": "doc2.pdf",
            "content": "content2",
            "category": "report",
            "project": "beta",
        },
    )

    # Filter by project alpha
    response = client.get("/documents/list?user_id=user_123&project=alpha")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["project"] == "alpha"
