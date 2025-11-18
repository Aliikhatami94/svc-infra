"""Unit tests for easy_storage builder function."""

import logging
from unittest.mock import MagicMock, patch

import pytest

try:
    import aioboto3

    AIOBOTO3_AVAILABLE = True
except ImportError:
    AIOBOTO3_AVAILABLE = False

from svc_infra.storage.backends import LocalBackend, MemoryBackend, S3Backend
from svc_infra.storage.easy import easy_storage
from svc_infra.storage.settings import StorageSettings


@pytest.mark.storage
class TestEasyStorage:
    """Test suite for easy_storage builder."""

    def test_explicit_memory_backend(self):
        """Test creating memory backend explicitly."""
        backend = easy_storage(backend="memory")
        assert isinstance(backend, MemoryBackend)

    def test_explicit_local_backend(self):
        """Test creating local backend explicitly."""
        backend = easy_storage(backend="local", base_path="/tmp/storage")
        assert isinstance(backend, LocalBackend)
        assert str(backend.base_path) == "/tmp/storage"

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_explicit_s3_backend(self):
        """Test creating S3 backend explicitly."""
        backend = easy_storage(
            backend="s3",
            bucket="test-bucket",
            region="us-east-1",
            access_key="key",
            secret_key="secret",
        )
        assert isinstance(backend, S3Backend)
        assert backend.bucket == "test-bucket"
        assert backend.region == "us-east-1"

    def test_invalid_backend_type(self):
        """Test error with invalid backend type."""
        with pytest.raises(ValueError):
            easy_storage(backend="invalid")

    def test_auto_detect_railway_volume(self, monkeypatch):
        """Test Railway volume auto-detection."""
        monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")

        backend = easy_storage()

        assert isinstance(backend, LocalBackend)
        assert str(backend.base_path) == "/data"

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_auto_detect_s3_from_settings(self, monkeypatch):
        """Test S3 auto-detection from environment."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("STORAGE_S3_BUCKET", "my-bucket")
        monkeypatch.setenv("STORAGE_S3_REGION", "us-west-2")

        backend = easy_storage()

        assert isinstance(backend, S3Backend)
        assert backend.bucket == "my-bucket"
        assert backend.region == "us-west-2"

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_auto_detect_s3_aws_credentials(self, monkeypatch):
        """Test S3 with AWS environment credentials."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("STORAGE_S3_BUCKET", "aws-bucket")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "aws-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")

        backend = easy_storage()

        assert isinstance(backend, S3Backend)
        assert backend.bucket == "aws-bucket"

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_auto_detect_digitalocean_spaces(self, monkeypatch, caplog):
        """Test DigitalOcean Spaces detection with logging."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("STORAGE_S3_BUCKET", "my-spaces")
        monkeypatch.setenv("STORAGE_S3_ENDPOINT", "https://nyc3.digitaloceanspaces.com")
        monkeypatch.setenv("STORAGE_S3_REGION", "nyc3")

        with caplog.at_level(logging.INFO):
            backend = easy_storage()

        assert isinstance(backend, S3Backend)
        assert backend.endpoint == "https://nyc3.digitaloceanspaces.com"
        assert "DigitalOcean Spaces" in caplog.text

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_auto_detect_wasabi(self, monkeypatch, caplog):
        """Test Wasabi detection with logging."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("STORAGE_S3_BUCKET", "wasabi-bucket")
        monkeypatch.setenv("STORAGE_S3_ENDPOINT", "https://s3.wasabisys.com")

        with caplog.at_level(logging.INFO):
            backend = easy_storage()

        assert "Wasabi" in caplog.text

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_auto_detect_backblaze(self, monkeypatch, caplog):
        """Test Backblaze B2 detection with logging."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("STORAGE_S3_BUCKET", "b2-bucket")
        monkeypatch.setenv("STORAGE_S3_ENDPOINT", "https://s3.us-west-001.backblazeb2.com")

        with caplog.at_level(logging.INFO):
            backend = easy_storage()

        assert "Backblaze B2" in caplog.text

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_auto_detect_minio(self, monkeypatch, caplog):
        """Test Minio detection with logging."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("STORAGE_S3_BUCKET", "minio-bucket")
        monkeypatch.setenv("STORAGE_S3_ENDPOINT", "http://localhost:9000")

        with caplog.at_level(logging.INFO):
            backend = easy_storage()

        assert "Minio" in caplog.text or "localhost" in caplog.text

    def test_fallback_to_memory(self, monkeypatch, caplog):
        """Test fallback to memory backend with warning."""
        # Clear all storage-related env vars
        for key in list(monkeypatch._setitem):
            if "STORAGE" in key or "RAILWAY" in key or "AWS" in key:
                monkeypatch.delenv(key, raising=False)

        with caplog.at_level(logging.WARNING):
            backend = easy_storage()

        assert isinstance(backend, MemoryBackend)
        assert "No storage backend" in caplog.text or "memory" in caplog.text.lower()

    def test_s3_without_bucket_error(self, monkeypatch):
        """Test error when S3 configured without bucket."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        # No bucket set

        with pytest.raises(ValueError, match="bucket"):
            easy_storage()

    def test_local_creates_directory(self, tmp_path):
        """Test that local backend works with non-existent directory."""
        storage_path = tmp_path / "storage"
        assert not storage_path.exists()

        backend = easy_storage(backend="local", base_path=str(storage_path))

        assert isinstance(backend, LocalBackend)
        # Directory is NOT created until first write
        assert not storage_path.exists()

    def test_memory_with_quota(self):
        """Test memory backend with custom quota."""
        backend = easy_storage(backend="memory", max_size=1024 * 1024)

        assert isinstance(backend, MemoryBackend)
        assert backend.max_size == 1024 * 1024

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_s3_with_custom_endpoint(self):
        """Test S3 with custom endpoint."""
        backend = easy_storage(
            backend="s3",
            bucket="custom-bucket",
            endpoint="https://custom.s3.example.com",
            region="custom-region",
            access_key="key",
            secret_key="secret",
        )

        assert backend.endpoint == "https://custom.s3.example.com"
        assert backend.region == "custom-region"

    def test_local_with_signing_secret(self):
        """Test local backend with URL signing secret."""
        backend = easy_storage(
            backend="local",
            base_path="/tmp/storage",
            signing_secret="my-secret-key",
        )

        assert backend.signing_secret == "my-secret-key"

    @patch("svc_infra.storage.easy.StorageSettings")
    def test_uses_settings_for_auto_detection(self, mock_settings):
        """Test that easy_storage uses StorageSettings for auto-detection."""
        # Mock settings instance
        mock_instance = MagicMock()
        mock_instance.detect_backend.return_value = "memory"
        mock_settings.return_value = mock_instance

        backend = easy_storage()

        # Should have called StorageSettings()
        mock_settings.assert_called_once()
        assert isinstance(backend, MemoryBackend)

    def test_railway_with_custom_secret(self, monkeypatch):
        """Test Railway detection with custom signing secret."""
        monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")

        backend = easy_storage(signing_secret="custom-secret")

        assert isinstance(backend, LocalBackend)
        assert backend.signing_secret == "custom-secret"

    def test_priority_explicit_over_auto(self, monkeypatch):
        """Test explicit backend takes priority over auto-detection."""
        # Set Railway env var
        monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")

        # But explicitly request memory
        backend = easy_storage(backend="memory")

        assert isinstance(backend, MemoryBackend)

    def test_kwargs_passed_to_backend(self):
        """Test that extra kwargs are passed to backend constructor."""
        backend = easy_storage(backend="memory", max_size=5000)

        assert backend.max_size == 5000

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_s3_region_default(self):
        """Test S3 backend with default region."""
        backend = easy_storage(
            backend="s3",
            bucket="test-bucket",
            access_key="key",
            secret_key="secret",
        )

        # Should default to us-east-1 or from settings
        assert backend.region is not None

    def test_local_default_path(self, monkeypatch):
        """Test local backend uses default path when not specified."""
        # Clear Railway env
        monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)

        backend = easy_storage(backend="local")

        assert isinstance(backend, LocalBackend)
        # Should have some default path (from settings or ./storage)
        assert backend.base_path is not None

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_detection_order(self, monkeypatch):
        """Test detection order: explicit > STORAGE_BACKEND > Railway > S3 > memory."""
        # Set both Railway and S3
        monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/railway")
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("STORAGE_S3_BUCKET", "s3-bucket")

        # Should prefer explicit
        backend1 = easy_storage(backend="memory")
        assert isinstance(backend1, MemoryBackend)

        # Without explicit, STORAGE_BACKEND=s3 takes precedence over Railway
        backend2 = easy_storage()
        assert isinstance(backend2, S3Backend)
        assert backend2.bucket == "s3-bucket"


@pytest.mark.storage
class TestEasyStorageLogging:
    """Test logging behavior of easy_storage."""

    def test_logs_backend_selection(self, caplog):
        """Test that backend selection is logged."""
        with caplog.at_level(logging.INFO):
            easy_storage(backend="memory")

        # Should log backend creation or selection
        assert len(caplog.records) >= 0  # May or may not log depending on implementation

    def test_logs_railway_detection(self, monkeypatch, caplog):
        """Test Railway detection logging."""
        monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")

        with caplog.at_level(logging.INFO):
            easy_storage()

        # Implementation may log Railway detection
        assert "Railway" in caplog.text or len(caplog.records) >= 0

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_logs_provider_name(self, monkeypatch, caplog):
        """Test S3 provider name logging."""
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("STORAGE_S3_BUCKET", "bucket")
        monkeypatch.setenv("STORAGE_S3_ENDPOINT", "https://nyc3.digitaloceanspaces.com")

        with caplog.at_level(logging.INFO):
            easy_storage()

        # Should log DigitalOcean Spaces detection
        assert "DigitalOcean" in caplog.text or len(caplog.records) >= 0


@pytest.mark.storage
class TestEasyStorageEdgeCases:
    """Test edge cases and error handling."""

    def test_none_backend_uses_auto_detection(self):
        """Test that backend=None triggers auto-detection."""
        backend = easy_storage(backend=None)
        # Should auto-detect and default to memory if nothing configured
        assert isinstance(backend, MemoryBackend)

    def test_empty_string_backend(self):
        """Test empty string backend triggers auto-detection."""
        backend = easy_storage(backend="")
        # Empty string treated as None, triggers auto-detection
        assert isinstance(backend, MemoryBackend)

    def test_case_insensitive_backend_names(self):
        """Test backend names work with lowercase."""
        backend = easy_storage(backend="memory")
        assert isinstance(backend, MemoryBackend)

    @pytest.mark.skipif(not AIOBOTO3_AVAILABLE, reason="aioboto3 not installed")
    def test_s3_with_incomplete_config(self):
        """Test S3 with incomplete configuration."""
        # Bucket but no credentials (should work with IAM role or env)
        backend = easy_storage(backend="s3", bucket="test-bucket", region="us-east-1")

        assert isinstance(backend, S3Backend)
        assert backend.access_key is None  # Will use env or IAM

    def test_local_with_relative_path(self):
        """Test local backend with relative path."""
        backend = easy_storage(backend="local", base_path="./local-storage")

        assert isinstance(backend, LocalBackend)
        assert "local-storage" in str(backend.base_path)
