"""Unit tests for svc_infra.deploy module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from svc_infra.deploy import (
    Platform,
    get_database_url,
    get_environment_name,
    get_host,
    get_platform,
    get_port,
    get_public_url,
    get_redis_url,
    get_service_url,
    is_aws,
    is_azure,
    is_containerized,
    is_gcp,
    is_local,
    is_paas,
    is_preview,
    is_production,
    is_serverless,
)


@pytest.fixture(autouse=True)
def clean_env() -> Generator[dict, None, None]:
    """Fixture that provides a clean environment for testing."""
    # Clear all platform-related env vars
    platform_vars = [
        # Developer PaaS
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
        "RAILWAY_PUBLIC_DOMAIN",
        "RENDER",
        "RENDER_SERVICE_ID",
        "RENDER_INSTANCE_ID",
        "RENDER_EXTERNAL_URL",
        "IS_PULL_REQUEST",
        "FLY_APP_NAME",
        "FLY_REGION",
        "FLY_ALLOC_ID",
        "DYNO",
        "HEROKU_APP_NAME",
        "HEROKU_SLUG_COMMIT",
        # AWS
        "AWS_LAMBDA_FUNCTION_NAME",
        "LAMBDA_TASK_ROOT",
        "ECS_CONTAINER_METADATA_URI",
        "ECS_CONTAINER_METADATA_URI_V4",
        "ELASTIC_BEANSTALK_ENVIRONMENT_NAME",
        # Google Cloud
        "K_SERVICE",
        "K_REVISION",
        "K_CONFIGURATION",
        "GAE_APPLICATION",
        "GAE_SERVICE",
        "GAE_VERSION",
        "GCE_METADATA_HOST",
        # Azure
        "CONTAINER_APP_NAME",
        "CONTAINER_APP_ENV_DNS_SUFFIX",
        "FUNCTIONS_WORKER_RUNTIME",
        "AzureWebJobsStorage",
        "WEBSITE_SITE_NAME",
        "WEBSITE_INSTANCE_ID",
        # Kubernetes/Docker
        "KUBERNETES_SERVICE_HOST",
        "KUBERNETES_PORT",
        "DOCKER_CONTAINER",
        # Server binding
        "PORT",
        "HOST",
        # Database
        "DATABASE_URL",
        "DATABASE_URL_PRIVATE",
        "SQL_URL",
        "DB_URL",
        "PRIVATE_SQL_URL",
        # Redis
        "REDIS_URL",
        "REDIS_URL_PRIVATE",
        "REDIS_PRIVATE_URL",
        "CACHE_URL",
        "UPSTASH_REDIS_REST_URL",
        # Environment
        "APP_ENV",
        "ENVIRONMENT",
        "ENV",
        "APP_URL",
        # Service discovery vars used in tests
        "WORKER_URL",
        "WORKER_SERVICE_HOST",
        "WORKER_SERVICE_PORT",
        "MY_WORKER_URL",
    ]

    original = {}
    for var in platform_vars:
        original[var] = os.environ.pop(var, None)

    # Clear the cached get_platform result
    get_platform.cache_clear()

    yield original

    # Restore original values
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]

    get_platform.cache_clear()


# =============================================================================
# Platform Detection Tests
# =============================================================================


class TestGetPlatform:
    """Tests for get_platform()."""

    def test_detects_railway(self, clean_env):
        """Detects Railway from environment."""
        os.environ["RAILWAY_PROJECT_ID"] = "abc123"
        get_platform.cache_clear()
        assert get_platform() == Platform.RAILWAY

    def test_detects_render(self, clean_env):
        """Detects Render from environment."""
        os.environ["RENDER"] = "true"
        get_platform.cache_clear()
        assert get_platform() == Platform.RENDER

    def test_detects_fly(self, clean_env):
        """Detects Fly.io from environment."""
        os.environ["FLY_APP_NAME"] = "my-app"
        get_platform.cache_clear()
        assert get_platform() == Platform.FLY

    def test_detects_heroku(self, clean_env):
        """Detects Heroku from environment."""
        os.environ["DYNO"] = "web.1"
        get_platform.cache_clear()
        assert get_platform() == Platform.HEROKU

    def test_detects_kubernetes(self, clean_env):
        """Detects Kubernetes from environment."""
        os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        get_platform.cache_clear()
        assert get_platform() == Platform.KUBERNETES

    def test_defaults_to_local(self, clean_env):
        """Defaults to LOCAL when no platform detected."""
        get_platform.cache_clear()
        assert get_platform() == Platform.LOCAL

    def test_railway_precedence(self, clean_env):
        """Railway detected first if multiple platforms set."""
        os.environ["RAILWAY_PROJECT_ID"] = "abc123"
        os.environ["RENDER"] = "true"
        get_platform.cache_clear()
        assert get_platform() == Platform.RAILWAY

    # AWS Platform Detection
    def test_detects_aws_lambda(self, clean_env):
        """Detects AWS Lambda from environment."""
        os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "my-function"
        get_platform.cache_clear()
        assert get_platform() == Platform.AWS_LAMBDA

    def test_detects_aws_ecs(self, clean_env):
        """Detects AWS ECS/Fargate from environment."""
        os.environ["ECS_CONTAINER_METADATA_URI"] = "http://169.254.170.2/v3"
        get_platform.cache_clear()
        assert get_platform() == Platform.AWS_ECS

    def test_detects_aws_beanstalk(self, clean_env):
        """Detects AWS Elastic Beanstalk from environment."""
        os.environ["ELASTIC_BEANSTALK_ENVIRONMENT_NAME"] = "my-env"
        get_platform.cache_clear()
        assert get_platform() == Platform.AWS_BEANSTALK

    # Google Cloud Platform Detection
    def test_detects_cloud_run(self, clean_env):
        """Detects Google Cloud Run from environment."""
        os.environ["K_SERVICE"] = "my-service"
        get_platform.cache_clear()
        assert get_platform() == Platform.CLOUD_RUN

    def test_detects_app_engine(self, clean_env):
        """Detects Google App Engine from environment."""
        os.environ["GAE_APPLICATION"] = "my-app"
        get_platform.cache_clear()
        assert get_platform() == Platform.APP_ENGINE

    # Azure Platform Detection
    def test_detects_azure_container_apps(self, clean_env):
        """Detects Azure Container Apps from environment."""
        os.environ["CONTAINER_APP_NAME"] = "my-app"
        get_platform.cache_clear()
        assert get_platform() == Platform.AZURE_CONTAINER_APPS

    def test_detects_azure_functions(self, clean_env):
        """Detects Azure Functions from environment."""
        os.environ["FUNCTIONS_WORKER_RUNTIME"] = "python"
        get_platform.cache_clear()
        assert get_platform() == Platform.AZURE_FUNCTIONS

    def test_detects_azure_app_service(self, clean_env):
        """Detects Azure App Service from environment."""
        os.environ["WEBSITE_SITE_NAME"] = "my-app"
        get_platform.cache_clear()
        assert get_platform() == Platform.AZURE_APP_SERVICE


class TestCloudProviderChecks:
    """Tests for cloud provider check functions."""

    def test_is_aws_true(self, clean_env):
        """is_aws() returns True for AWS platforms."""
        os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "my-function"
        get_platform.cache_clear()
        assert is_aws() is True

    def test_is_aws_false(self, clean_env):
        """is_aws() returns False for non-AWS platforms."""
        os.environ["RAILWAY_PROJECT_ID"] = "abc123"
        get_platform.cache_clear()
        assert is_aws() is False

    def test_is_gcp_true(self, clean_env):
        """is_gcp() returns True for GCP platforms."""
        os.environ["K_SERVICE"] = "my-service"
        get_platform.cache_clear()
        assert is_gcp() is True

    def test_is_gcp_false(self, clean_env):
        """is_gcp() returns False for non-GCP platforms."""
        os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "my-function"
        get_platform.cache_clear()
        assert is_gcp() is False

    def test_is_azure_true(self, clean_env):
        """is_azure() returns True for Azure platforms."""
        os.environ["CONTAINER_APP_NAME"] = "my-app"
        get_platform.cache_clear()
        assert is_azure() is True

    def test_is_azure_false(self, clean_env):
        """is_azure() returns False for non-Azure platforms."""
        os.environ["K_SERVICE"] = "my-service"
        get_platform.cache_clear()
        assert is_azure() is False

    def test_is_paas_true(self, clean_env):
        """is_paas() returns True for PaaS platforms."""
        os.environ["RAILWAY_PROJECT_ID"] = "abc123"
        get_platform.cache_clear()
        assert is_paas() is True

    def test_is_paas_false_for_aws(self, clean_env):
        """is_paas() returns False for cloud providers."""
        os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "my-function"
        get_platform.cache_clear()
        assert is_paas() is False

    def test_is_serverless_lambda(self, clean_env):
        """is_serverless() returns True for Lambda."""
        os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "my-function"
        get_platform.cache_clear()
        assert is_serverless() is True

    def test_is_serverless_cloud_run(self, clean_env):
        """is_serverless() returns True for Cloud Run."""
        os.environ["K_SERVICE"] = "my-service"
        get_platform.cache_clear()
        assert is_serverless() is True

    def test_is_serverless_functions(self, clean_env):
        """is_serverless() returns True for Azure Functions."""
        os.environ["FUNCTIONS_WORKER_RUNTIME"] = "python"
        get_platform.cache_clear()
        assert is_serverless() is True

    def test_is_serverless_false_for_ecs(self, clean_env):
        """is_serverless() returns False for ECS (container, not serverless)."""
        os.environ["ECS_CONTAINER_METADATA_URI"] = "http://169.254.170.2/v3"
        get_platform.cache_clear()
        assert is_serverless() is False


class TestIsContainerized:
    """Tests for is_containerized()."""

    def test_true_for_railway(self, clean_env):
        """Returns True for Railway."""
        os.environ["RAILWAY_PROJECT_ID"] = "abc123"
        get_platform.cache_clear()
        assert is_containerized() is True

    def test_true_for_kubernetes(self, clean_env):
        """Returns True for Kubernetes."""
        os.environ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        get_platform.cache_clear()
        assert is_containerized() is True

    def test_false_for_local(self, clean_env):
        """Returns False for local."""
        get_platform.cache_clear()
        assert is_containerized() is False


class TestIsLocal:
    """Tests for is_local()."""

    def test_true_when_local(self, clean_env):
        """Returns True for local environment."""
        get_platform.cache_clear()
        assert is_local() is True

    def test_false_when_deployed(self, clean_env):
        """Returns False when deployed."""
        os.environ["RAILWAY_PROJECT_ID"] = "abc123"
        get_platform.cache_clear()
        assert is_local() is False


# =============================================================================
# Server Binding Tests
# =============================================================================


class TestGetPort:
    """Tests for get_port()."""

    def test_returns_default_when_not_set(self, clean_env):
        """Returns default when PORT not set."""
        assert get_port() == 8000

    def test_returns_custom_default(self, clean_env):
        """Returns custom default when specified."""
        assert get_port(default=3000) == 3000

    def test_reads_port_env_var(self, clean_env):
        """Reads PORT environment variable."""
        os.environ["PORT"] = "5000"
        assert get_port() == 5000

    def test_ignores_non_numeric(self, clean_env):
        """Ignores non-numeric PORT value."""
        os.environ["PORT"] = "invalid"
        assert get_port() == 8000


class TestGetHost:
    """Tests for get_host()."""

    def test_returns_localhost_for_local(self, clean_env):
        """Returns localhost for local development."""
        get_platform.cache_clear()
        assert get_host() == "127.0.0.1"

    def test_returns_all_interfaces_for_container(self, clean_env):
        """Returns 0.0.0.0 for containerized environments."""
        os.environ["RAILWAY_PROJECT_ID"] = "abc123"
        get_platform.cache_clear()
        assert get_host() == "0.0.0.0"

    def test_respects_host_env_var(self, clean_env):
        """Respects HOST environment variable for local."""
        os.environ["HOST"] = "192.168.1.1"
        get_platform.cache_clear()
        assert get_host() == "192.168.1.1"

    def test_custom_default(self, clean_env):
        """Uses custom default for local."""
        get_platform.cache_clear()
        assert get_host(default="0.0.0.0") == "0.0.0.0"


# =============================================================================
# Database URL Tests
# =============================================================================


class TestGetDatabaseUrl:
    """Tests for get_database_url()."""

    def test_returns_none_when_not_set(self, clean_env):
        """Returns None when no database URL configured."""
        assert get_database_url() is None

    def test_prefers_private_url(self, clean_env):
        """Prefers DATABASE_URL_PRIVATE over DATABASE_URL."""
        os.environ["DATABASE_URL"] = "postgresql://public:5432/db"
        os.environ["DATABASE_URL_PRIVATE"] = "postgresql://private:5432/db"
        assert get_database_url() == "postgresql://private:5432/db"

    def test_falls_back_to_public(self, clean_env):
        """Falls back to DATABASE_URL when private not set."""
        os.environ["DATABASE_URL"] = "postgresql://public:5432/db"
        assert get_database_url() == "postgresql://public:5432/db"

    def test_respects_prefer_private_false(self, clean_env):
        """Respects prefer_private=False."""
        os.environ["DATABASE_URL"] = "postgresql://public:5432/db"
        os.environ["DATABASE_URL_PRIVATE"] = "postgresql://private:5432/db"
        assert get_database_url(prefer_private=False) == "postgresql://public:5432/db"

    def test_normalizes_postgres_url(self, clean_env):
        """Normalizes postgres:// to postgresql://."""
        os.environ["DATABASE_URL"] = "postgres://host:5432/db"
        assert get_database_url() == "postgresql://host:5432/db"

    def test_normalizes_postgres_asyncpg(self, clean_env):
        """Normalizes postgres+asyncpg:// to postgresql+asyncpg://."""
        os.environ["DATABASE_URL"] = "postgres+asyncpg://host:5432/db"
        assert get_database_url() == "postgresql+asyncpg://host:5432/db"

    def test_respects_normalize_false(self, clean_env):
        """Respects normalize=False."""
        os.environ["DATABASE_URL"] = "postgres://host:5432/db"
        assert get_database_url(normalize=False) == "postgres://host:5432/db"

    def test_legacy_sql_url(self, clean_env):
        """Falls back to legacy SQL_URL."""
        os.environ["SQL_URL"] = "postgresql://legacy:5432/db"
        assert get_database_url() == "postgresql://legacy:5432/db"


# =============================================================================
# Redis URL Tests
# =============================================================================


class TestGetRedisUrl:
    """Tests for get_redis_url()."""

    def test_returns_none_when_not_set(self, clean_env):
        """Returns None when no Redis URL configured."""
        assert get_redis_url() is None

    def test_prefers_private_url(self, clean_env):
        """Prefers REDIS_URL_PRIVATE over REDIS_URL."""
        os.environ["REDIS_URL"] = "redis://public:6379"
        os.environ["REDIS_URL_PRIVATE"] = "redis://private:6379"
        assert get_redis_url() == "redis://private:6379"

    def test_falls_back_to_public(self, clean_env):
        """Falls back to REDIS_URL when private not set."""
        os.environ["REDIS_URL"] = "redis://public:6379"
        assert get_redis_url() == "redis://public:6379"

    def test_supports_cache_url(self, clean_env):
        """Supports CACHE_URL as fallback."""
        os.environ["CACHE_URL"] = "redis://cache:6379"
        assert get_redis_url() == "redis://cache:6379"

    def test_supports_upstash(self, clean_env):
        """Supports Upstash Redis URL."""
        os.environ["UPSTASH_REDIS_REST_URL"] = "https://upstash.io/redis"
        assert get_redis_url() == "https://upstash.io/redis"


# =============================================================================
# Service Discovery Tests
# =============================================================================


class TestGetServiceUrl:
    """Tests for get_service_url()."""

    def test_returns_none_when_not_discoverable(self, clean_env):
        """Returns None when service not discoverable."""
        assert get_service_url("worker") is None

    def test_finds_direct_url(self, clean_env):
        """Finds service via direct URL env var."""
        os.environ["WORKER_URL"] = "http://worker:8000"
        assert get_service_url("worker") == "http://worker:8000"

    def test_finds_kubernetes_service(self, clean_env):
        """Finds service via Kubernetes env vars."""
        os.environ["WORKER_SERVICE_HOST"] = "10.0.0.5"
        os.environ["WORKER_SERVICE_PORT"] = "3000"
        assert get_service_url("worker") == "http://10.0.0.5:3000"

    def test_uses_default_port(self, clean_env):
        """Uses default port for Kubernetes when port not set."""
        os.environ["WORKER_SERVICE_HOST"] = "10.0.0.5"
        assert get_service_url("worker", default_port=9000) == "http://10.0.0.5:9000"

    def test_handles_dashes_in_name(self, clean_env):
        """Handles dashes in service name."""
        os.environ["MY_WORKER_URL"] = "http://my-worker:8000"
        assert get_service_url("my-worker") == "http://my-worker:8000"


class TestGetPublicUrl:
    """Tests for get_public_url()."""

    def test_returns_none_when_not_available(self, clean_env):
        """Returns None when no public URL available."""
        assert get_public_url() is None

    def test_railway_public_domain(self, clean_env):
        """Returns Railway public URL."""
        os.environ["RAILWAY_PUBLIC_DOMAIN"] = "my-app.up.railway.app"
        assert get_public_url() == "https://my-app.up.railway.app"

    def test_render_external_url(self, clean_env):
        """Returns Render external URL."""
        os.environ["RENDER_EXTERNAL_URL"] = "https://my-app.onrender.com"
        assert get_public_url() == "https://my-app.onrender.com"

    def test_fly_app_url(self, clean_env):
        """Returns Fly.io app URL."""
        os.environ["FLY_APP_NAME"] = "my-app"
        assert get_public_url() == "https://my-app.fly.dev"

    def test_heroku_app_url(self, clean_env):
        """Returns Heroku app URL."""
        os.environ["HEROKU_APP_NAME"] = "my-app"
        assert get_public_url() == "https://my-app.herokuapp.com"


# =============================================================================
# Environment Name Tests
# =============================================================================


class TestGetEnvironmentName:
    """Tests for get_environment_name()."""

    def test_returns_local_by_default(self, clean_env):
        """Returns 'local' by default."""
        assert get_environment_name() == "local"

    def test_reads_railway_environment(self, clean_env):
        """Reads RAILWAY_ENVIRONMENT."""
        os.environ["RAILWAY_ENVIRONMENT"] = "Production"
        assert get_environment_name() == "production"

    def test_render_preview_detection(self, clean_env):
        """Detects Render preview environment."""
        os.environ["RENDER"] = "true"
        os.environ["IS_PULL_REQUEST"] = "true"
        assert get_environment_name() == "preview"

    def test_render_production(self, clean_env):
        """Detects Render production."""
        os.environ["RENDER"] = "true"
        assert get_environment_name() == "production"

    def test_reads_app_env(self, clean_env):
        """Reads APP_ENV."""
        os.environ["APP_ENV"] = "staging"
        assert get_environment_name() == "staging"


class TestIsProduction:
    """Tests for is_production()."""

    def test_true_for_production(self, clean_env):
        """Returns True for production."""
        os.environ["APP_ENV"] = "production"
        assert is_production() is True

    def test_true_for_prod(self, clean_env):
        """Returns True for prod."""
        os.environ["APP_ENV"] = "prod"
        assert is_production() is True

    def test_false_for_staging(self, clean_env):
        """Returns False for staging."""
        os.environ["APP_ENV"] = "staging"
        assert is_production() is False


class TestIsPreview:
    """Tests for is_preview()."""

    def test_true_for_preview(self, clean_env):
        """Returns True for preview."""
        os.environ["APP_ENV"] = "preview"
        assert is_preview() is True

    def test_true_for_staging(self, clean_env):
        """Returns True for staging."""
        os.environ["APP_ENV"] = "staging"
        assert is_preview() is True

    def test_false_for_production(self, clean_env):
        """Returns False for production."""
        os.environ["APP_ENV"] = "production"
        assert is_preview() is False
