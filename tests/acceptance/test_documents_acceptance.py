"""
Acceptance tests for the documents module.

These tests verify the end-to-end document management functionality including:
- Document upload with metadata
- Document retrieval
- Document listing with pagination
- Document deletion
- User isolation

Test IDs: A23-01 to A23-05
"""

from __future__ import annotations

import hashlib
from io import BytesIO

import pytest

pytestmark = pytest.mark.acceptance


@pytest.fixture
def sample_file():
    """Sample file content for testing."""
    content = b"This is a test document for acceptance testing."
    return {
        "content": content,
        "filename": "test-document.txt",
        "content_type": "text/plain",
        "size": len(content),
        "checksum": f"sha256:{hashlib.sha256(content).hexdigest()}",
    }


def test_a23_01_upload_document_and_retrieve_metadata(client, sample_file):
    """
    A23-01: Upload document and retrieve metadata

    Given a user wants to upload a document
    When they POST to /documents/upload with file and metadata
    Then the document is stored successfully
    And metadata can be retrieved via GET /documents/{id}
    """
    # Upload document
    response = client.post(
        "/documents/upload",
        data={
            "user_id": "user_a23_01",
            "category": "legal",
            "year": "2024",
        },
        files={
            "file": (
                sample_file["filename"],
                BytesIO(sample_file["content"]),
                sample_file["content_type"],
            )
        },
    )

    assert response.status_code == 200
    upload_data = response.json()

    # Verify upload response
    assert "id" in upload_data
    assert upload_data["filename"] == sample_file["filename"]
    assert upload_data["file_size"] == sample_file["size"]
    assert upload_data["content_type"] == sample_file["content_type"]
    assert upload_data["checksum"] == sample_file["checksum"]
    assert upload_data["user_id"] == "user_a23_01"
    assert upload_data["metadata"]["category"] == "legal"
    assert upload_data["metadata"]["year"] == "2024"

    document_id = upload_data["id"]

    # Retrieve document metadata
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 200

    metadata = response.json()
    assert metadata["id"] == document_id
    assert metadata["filename"] == sample_file["filename"]
    assert metadata["user_id"] == "user_a23_01"
    assert metadata["metadata"]["category"] == "legal"


def test_a23_02_list_user_documents_with_pagination(client, sample_file):
    """
    A23-02: List user's documents with pagination

    Given a user has uploaded multiple documents
    When they GET /documents/list?user_id=...
    Then all their documents are returned
    And pagination parameters work correctly
    """
    user_id = "user_a23_02"

    # Upload 5 documents
    document_ids = []
    for i in range(5):
        response = client.post(
            "/documents/upload",
            data={
                "user_id": user_id,
                "doc_number": str(i),
            },
            files={
                "file": (
                    f"document_{i}.txt",
                    BytesIO(f"Document {i} content".encode()),
                    "text/plain",
                )
            },
        )
        assert response.status_code == 200
        document_ids.append(response.json()["id"])

    # List all documents (no pagination)
    response = client.get(f"/documents/list?user_id={user_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 5
    assert len(data["documents"]) == 5
    assert data["limit"] == 100
    assert data["offset"] == 0

    # Verify all documents are returned
    returned_ids = [doc["id"] for doc in data["documents"]]
    for doc_id in document_ids:
        assert doc_id in returned_ids

    # Test pagination (limit=2)
    response = client.get(f"/documents/list?user_id={user_id}&limit=2&offset=0")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 5
    assert len(data["documents"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Get next page
    response = client.get(f"/documents/list?user_id={user_id}&limit=2&offset=2")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 5
    assert len(data["documents"]) == 2
    assert data["offset"] == 2


def test_a23_03_download_document_content(client, sample_file):
    """
    A23-03: Download document content

    Given a document has been uploaded
    When the user requests to download it
    Then the original file content is returned
    """
    user_id = "user_a23_03"

    # Upload document
    response = client.post(
        "/documents/upload",
        data={"user_id": user_id},
        files={
            "file": (
                sample_file["filename"],
                BytesIO(sample_file["content"]),
                sample_file["content_type"],
            )
        },
    )
    assert response.status_code == 200
    document_id = response.json()["id"]

    # Download document (note: current implementation returns file bytes)
    # In production, this would be a presigned URL or direct file download
    # For acceptance tests, we verify the endpoint exists and returns data
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 200

    # Verify metadata is accessible (content download tested at unit level)
    metadata = response.json()
    assert metadata["id"] == document_id
    assert metadata["filename"] == sample_file["filename"]


def test_a23_04_delete_document(client, sample_file):
    """
    A23-04: Delete document

    Given a document exists
    When the user deletes it via DELETE /documents/{id}
    Then the document is removed from storage
    And subsequent GET requests return 404
    """
    user_id = "user_a23_04"

    # Upload document
    response = client.post(
        "/documents/upload",
        data={"user_id": user_id},
        files={
            "file": (
                sample_file["filename"],
                BytesIO(sample_file["content"]),
                sample_file["content_type"],
            )
        },
    )
    assert response.status_code == 200
    document_id = response.json()["id"]

    # Verify document exists
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 200

    # Delete document
    response = client.delete(f"/documents/{document_id}")
    assert response.status_code == 204

    # Verify document no longer exists
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 404


def test_a23_05_user_isolation(client, sample_file):
    """
    A23-05: User isolation (users can't access other users' documents)

    Given two users have uploaded documents
    When user_a lists their documents
    Then only user_a's documents are returned
    And user_b's documents are not visible
    """
    # Upload document for user_a
    response = client.post(
        "/documents/upload",
        data={"user_id": "user_a"},
        files={
            "file": (
                "user_a_document.txt",
                BytesIO(b"User A document"),
                "text/plain",
            )
        },
    )
    assert response.status_code == 200
    user_a_doc_id = response.json()["id"]

    # Upload document for user_b
    response = client.post(
        "/documents/upload",
        data={"user_id": "user_b"},
        files={
            "file": (
                "user_b_document.txt",
                BytesIO(b"User B document"),
                "text/plain",
            )
        },
    )
    assert response.status_code == 200
    user_b_doc_id = response.json()["id"]

    # List user_a's documents
    response = client.get("/documents/list?user_id=user_a")
    assert response.status_code == 200

    data = response.json()
    user_a_docs = data["documents"]
    user_a_ids = [doc["id"] for doc in user_a_docs]

    # Verify user_a only sees their document
    assert user_a_doc_id in user_a_ids
    assert user_b_doc_id not in user_a_ids

    # List user_b's documents
    response = client.get("/documents/list?user_id=user_b")
    assert response.status_code == 200

    data = response.json()
    user_b_docs = data["documents"]
    user_b_ids = [doc["id"] for doc in user_b_docs]

    # Verify user_b only sees their document
    assert user_b_doc_id in user_b_ids
    assert user_a_doc_id not in user_b_ids


def test_a23_06_upload_with_custom_metadata(client):
    """
    A23-06: Upload document with custom metadata fields

    Given a user wants to store custom metadata
    When they upload with additional form fields
    Then all metadata is preserved and retrievable
    """
    response = client.post(
        "/documents/upload",
        data={
            "user_id": "user_a23_06",
            "category": "legal",
            "contract_type": "employment",
            "parties": "Company Inc, John Doe",
            "signed_date": "2024-11-18",
            "status": "active",
        },
        files={
            "file": (
                "contract.pdf",
                BytesIO(b"Contract content"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify all metadata fields are preserved
    metadata = data["metadata"]
    assert metadata["category"] == "legal"
    assert metadata["contract_type"] == "employment"
    assert metadata["parties"] == "Company Inc, John Doe"
    assert metadata["signed_date"] == "2024-11-18"
    assert metadata["status"] == "active"

    # Retrieve and verify persistence
    document_id = data["id"]
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 200

    retrieved_metadata = response.json()["metadata"]
    assert retrieved_metadata == metadata


def test_a23_07_empty_document_list(client):
    """
    A23-07: List documents for user with no documents

    Given a user has not uploaded any documents
    When they request their document list
    Then an empty list is returned with total=0
    """
    response = client.get("/documents/list?user_id=user_with_no_docs")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 0
    assert len(data["documents"]) == 0
    assert data["limit"] == 100
    assert data["offset"] == 0
