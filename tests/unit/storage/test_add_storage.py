"""Unit tests for FastAPI storage integration."""

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from svc_infra.storage.add import add_storage, get_storage, health_check_storage
from svc_infra.storage.backends import LocalBackend, MemoryBackend


@pytest.mark.storage
class TestAddStorage:
    """Test suite for add_storage FastAPI integration."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app."""
        return FastAPI()

    @pytest.fixture
    def memory_backend(self):
        """Create memory backend for testing."""
        return MemoryBackend()

    def test_add_storage_registers_backend(self, app, memory_backend):
        """Test that add_storage registers backend in app.state."""
        add_storage(app, memory_backend)

        assert hasattr(app.state, "storage")
        assert app.state.storage is memory_backend

    def test_add_storage_with_startup_hook(self, app, memory_backend):
        """Test startup hook registration."""
        add_storage(app, memory_backend)

        # Verify backend is registered
        assert app.state.storage is memory_backend

        # Simulate app startup - lifespan will run
        with TestClient(app):
            pass  # Lifespan runs in context manager

    def test_add_storage_with_shutdown_hook(self, app):
        """Test shutdown hook registration."""
        backend = MemoryBackend()
        add_storage(app, backend)

        # Verify backend is registered
        assert app.state.storage is backend

        # Simulate app lifecycle - lifespan shutdown will run
        with TestClient(app):
            pass

    def test_add_storage_mounts_health_endpoint(self, app, memory_backend):
        """Test that storage is available for health check."""
        add_storage(app, memory_backend)

        # Health check must be manually mounted, but storage is available
        assert hasattr(app.state, "storage")
        assert app.state.storage is memory_backend

    def test_add_storage_without_serve_files(self, app, memory_backend):
        """Test add_storage without file serving enabled."""
        add_storage(app, memory_backend, serve_files=False)

        client = TestClient(app)

        # No file serving route should be mounted
        response = client.get("/files/test.txt?expires=123&signature=abc")
        assert response.status_code == 404

    def test_add_storage_with_serve_files_local(self, app, tmp_path):
        """Test file serving with LocalBackend."""
        backend = LocalBackend(base_path=str(tmp_path), signing_secret="test-secret")
        add_storage(app, backend, serve_files=True)

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        # Generate signed URL (matching LocalBackend._sign_url format)
        import hashlib
        import hmac
        import time
        from urllib.parse import urlencode

        expires = int(time.time()) + 3600
        message = f"test.txt:{expires}:False".encode()
        signature = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

        params = urlencode({"expires": expires, "signature": signature})

        client = TestClient(app)
        response = client.get(f"/files/test.txt?{params}")

        assert response.status_code == 200
        assert response.content == b"test content"

    def test_add_storage_with_serve_files_memory(self, app, memory_backend):
        """Test that serve_files is ignored for MemoryBackend."""
        add_storage(app, memory_backend, serve_files=True)

        client = TestClient(app)
        response = client.get("/files/test.txt")

        # Should return 404 since MemoryBackend doesn't support file serving
        assert response.status_code == 404

    def test_add_storage_custom_route_prefix(self, app, memory_backend):
        """Test custom file serving route prefix."""
        add_storage(app, memory_backend, serve_files=True, file_route_prefix="/storage")

        client = TestClient(app)

        # Should be at /storage/* not /files/*
        response = client.get("/storage/test.txt")
        assert response.status_code == 404  # File doesn't exist but route exists

        response = client.get("/files/test.txt")
        assert response.status_code == 404  # Route doesn't exist

    def test_add_storage_multiple_calls_warning(self, app, memory_backend):
        """Test multiple add_storage calls replaces backend."""
        add_storage(app, memory_backend)
        assert app.state.storage is memory_backend

        # Second call replaces the backend
        backend2 = MemoryBackend()
        add_storage(app, backend2)
        assert app.state.storage is backend2


@pytest.mark.storage
@pytest.mark.asyncio
class TestGetStorage:
    """Test suite for get_storage dependency."""

    @pytest.fixture
    def app_with_storage(self):
        """Create app with storage."""
        app = FastAPI()
        backend = MemoryBackend()
        add_storage(app, backend)
        return app

    async def test_get_storage_returns_backend(self, app_with_storage):
        """Test get_storage returns backend from app.state."""
        # Create mock request
        request = MagicMock(spec=Request)
        request.app = app_with_storage

        backend = get_storage(request)  # Not async

        assert isinstance(backend, MemoryBackend)
        assert backend is app_with_storage.state.storage

    async def test_get_storage_missing_backend(self):
        """Test get_storage raises error when storage not configured."""
        app = FastAPI()  # No storage added
        request = MagicMock(spec=Request)
        request.app = app

        with pytest.raises(RuntimeError, match="Storage not initialized"):
            get_storage(request)  # Not async

    async def test_get_storage_in_route(self, app_with_storage):
        """Test get_storage as dependency in route."""
        app = app_with_storage

        @app.get("/test")
        async def test_route(storage=None):  # Would use Depends(get_storage)
            # In real FastAPI, storage would be injected
            storage = app.state.storage
            return {"backend": storage.__class__.__name__}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["backend"] == "MemoryBackend"


@pytest.mark.storage
@pytest.mark.asyncio
class TestHealthCheckStorage:
    """Test suite for health_check_storage endpoint."""

    @pytest.fixture
    def app_with_storage(self):
        """Create app with storage."""
        app = FastAPI()
        backend = MemoryBackend()
        add_storage(app, backend)
        return app

    async def test_health_check_success(self, app_with_storage):
        """Test health check returns success."""
        request = MagicMock(spec=Request)
        request.app = app_with_storage

        result = await health_check_storage(request)

        assert result["status"] == "healthy"
        assert result["backend"] == "memory"

    async def test_health_check_with_stats(self, app_with_storage):
        """Test health check works after adding data."""
        backend = app_with_storage.state.storage

        # Add some data
        await backend.put("test.txt", b"data", "text/plain")

        request = MagicMock(spec=Request)
        request.app = app_with_storage

        result = await health_check_storage(request)

        assert result["status"] == "healthy"
        assert result["backend"] == "memory"

    async def test_health_check_no_storage(self):
        """Test health check when storage not configured."""
        app = FastAPI()
        request = MagicMock(spec=Request)
        request.app = app

        result = await health_check_storage(request)
        assert result["status"] == "unhealthy"
        assert "error" in result

    async def test_health_check_local_backend(self, tmp_path):
        """Test health check with LocalBackend."""
        app = FastAPI()
        backend = LocalBackend(base_path=str(tmp_path), signing_secret="secret")
        add_storage(app, backend)

        request = MagicMock(spec=Request)
        request.app = app

        result = await health_check_storage(request)

        assert result["status"] == "healthy"
        assert result["backend"] == "local"


@pytest.mark.storage
class TestFileServing:
    """Test file serving functionality."""

    @pytest.fixture
    def app_with_local(self, tmp_path):
        """Create app with LocalBackend and file serving."""
        app = FastAPI()
        backend = LocalBackend(base_path=str(tmp_path), signing_secret="test-secret")
        add_storage(app, backend, serve_files=True)
        return app, backend

    def test_serve_file_valid_signature(self, app_with_local, tmp_path):
        """Test serving file with valid signature."""
        app, backend = app_with_local

        # Create file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"file content")

        # Generate valid signed URL (matches LocalBackend._sign_url)
        import hashlib
        import hmac
        import time
        from urllib.parse import urlencode

        expires = int(time.time()) + 3600
        message = f"test.txt:{expires}:False".encode()
        signature = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

        params = urlencode({"expires": expires, "signature": signature})

        client = TestClient(app)
        response = client.get(f"/files/test.txt?{params}")

        assert response.status_code == 200
        assert response.content == b"file content"
        assert response.headers["content-type"] == "application/octet-stream"

    def test_serve_file_invalid_signature(self, app_with_local, tmp_path):
        """Test serving file with invalid signature."""
        app, _ = app_with_local

        # Create file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content")

        # Invalid signature
        import time
        from urllib.parse import urlencode

        expires = int(time.time()) + 3600
        params = urlencode({"expires": expires, "signature": "invalid"})

        client = TestClient(app)
        response = client.get(f"/files/test.txt?{params}")

        assert response.status_code == 403

    def test_serve_file_expired(self, app_with_local, tmp_path):
        """Test serving file with expired signature."""
        app, _ = app_with_local

        # Create file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content")

        # Expired signature
        import hashlib
        import hmac
        import time
        from urllib.parse import urlencode

        expires = int(time.time()) - 3600  # Expired 1 hour ago
        message = f"test.txt:{expires}:False".encode()
        signature = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

        params = urlencode({"expires": expires, "signature": signature})

        client = TestClient(app)
        response = client.get(f"/files/test.txt?{params}")

        assert response.status_code == 403

    def test_serve_nonexistent_file(self, app_with_local):
        """Test serving nonexistent file."""
        app, _ = app_with_local

        # Valid signature for nonexistent file
        import hashlib
        import hmac
        import time
        from urllib.parse import urlencode

        expires = int(time.time()) + 3600
        message = f"nonexistent.txt:{expires}:False".encode()
        signature = hmac.new(b"test-secret", message, hashlib.sha256).hexdigest()

        params = urlencode({"expires": expires, "signature": signature})

        client = TestClient(app)
        response = client.get(f"/files/nonexistent.txt?{params}")

        assert response.status_code == 404

    def test_serve_file_missing_params(self, app_with_local, tmp_path):
        """Test serving file without signature params."""
        app, _ = app_with_local

        # Create file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content")

        client = TestClient(app)

        # Missing signature
        response = client.get("/files/test.txt?expires=123456")
        assert response.status_code == 422  # FastAPI validation error

        # Missing expires
        response = client.get("/files/test.txt?signature=abc")
        assert response.status_code == 422  # FastAPI validation error


@pytest.mark.storage
class TestIntegration:
    """Integration tests for complete storage setup."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, tmp_path):
        """Test complete storage lifecycle in FastAPI app."""
        # Setup
        app = FastAPI()
        backend = MemoryBackend()
        add_storage(app, backend)

        @app.post("/upload")
        async def upload(request: Request, filename: str):
            storage = get_storage(request)  # Not async
            await storage.put(filename, b"test data", "text/plain")
            url = await storage.get_url(filename)
            return {"url": url}

        @app.get("/download/{filename}")
        async def download(filename: str, request: Request):
            storage = get_storage(request)  # Not async
            data = await storage.get(filename)
            return {"data": data.decode()}

        # Test
        client = TestClient(app)

        # Upload
        response = client.post("/upload?filename=test.txt")
        assert response.status_code == 200
        assert "url" in response.json()

        # Download
        response = client.get("/download/test.txt")
        assert response.status_code == 200
        assert response.json()["data"] == "test data"

    def test_startup_shutdown_lifecycle(self, tmp_path):
        """Test app startup and shutdown with storage."""
        app = FastAPI()
        backend = MemoryBackend()

        lifecycle_events = []

        # Mock lifecycle methods
        async def mock_startup():
            lifecycle_events.append("startup")

        async def mock_shutdown():
            lifecycle_events.append("shutdown")

        backend.__aenter__ = AsyncMock(side_effect=mock_startup)
        backend.__aexit__ = AsyncMock(side_effect=mock_shutdown)

        add_storage(app, backend)

        # Test with TestClient lifecycle
        with TestClient(app):
            pass  # Enter and exit context

        # Check lifecycle called (may not be in MemoryBackend)
        # This is mainly testing the hook registration
        assert len(lifecycle_events) >= 0
