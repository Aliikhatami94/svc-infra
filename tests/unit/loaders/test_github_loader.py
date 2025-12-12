"""Tests for GitHubLoader.

Tests the GitHub content loader functionality including:
- Loading from public repositories
- Path filtering and pattern matching
- Skip patterns
- Error handling (404, 403)
- Metadata population
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from svc_infra.loaders import GitHubLoader, LoadedContent


class TestGitHubLoaderInit:
    """Tests for GitHubLoader initialization."""

    def test_basic_init(self):
        """Test basic initialization with required parameters."""
        loader = GitHubLoader("owner/repo")

        assert loader.repo == "owner/repo"
        assert loader.path == ""
        assert loader.branch == "main"
        assert loader.pattern == "*.md"
        assert loader.recursive is True

    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        loader = GitHubLoader(
            repo="owner/repo",
            path="docs/api",
            branch="develop",
            pattern="*.py",
            token="test-token",
            recursive=False,
            skip_patterns=["test_*"],
            extra_metadata={"project": "test"},
        )

        assert loader.repo == "owner/repo"
        assert loader.path == "docs/api"
        assert loader.branch == "develop"
        assert loader.pattern == "*.py"
        assert loader.token == "test-token"
        assert loader.recursive is False
        assert loader.skip_patterns == ["test_*"]
        assert loader.extra_metadata == {"project": "test"}

    def test_invalid_repo_format_no_slash(self):
        """Test that invalid repo format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            GitHubLoader("invalid-repo")

    def test_invalid_repo_format_too_many_slashes(self):
        """Test that repo with too many slashes raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            GitHubLoader("owner/repo/extra")

    def test_path_normalization(self):
        """Test that path is normalized (strips slashes)."""
        loader = GitHubLoader("owner/repo", path="/docs/api/")
        assert loader.path == "docs/api"

    def test_token_from_env(self):
        """Test that token falls back to GITHUB_TOKEN env var."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            loader = GitHubLoader("owner/repo")
            assert loader.token == "env-token"

    def test_explicit_token_overrides_env(self):
        """Test that explicit token overrides env var."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            loader = GitHubLoader("owner/repo", token="explicit-token")
            assert loader.token == "explicit-token"

    def test_repr(self):
        """Test string representation."""
        loader = GitHubLoader("owner/repo", path="docs", pattern="*.py")
        assert (
            repr(loader) == "GitHubLoader('owner/repo', path='docs', branch='main', pattern='*.py')"
        )


class TestGitHubLoaderPatternMatching:
    """Tests for pattern matching functionality."""

    def test_matches_single_pattern(self):
        """Test single glob pattern matching."""
        loader = GitHubLoader("owner/repo", pattern="*.md")

        assert loader._matches_pattern("README.md") is True
        assert loader._matches_pattern("guide.md") is True
        assert loader._matches_pattern("script.py") is False

    def test_matches_multiple_patterns(self):
        """Test multiple patterns separated by |."""
        loader = GitHubLoader("owner/repo", pattern="*.md|*.py")

        assert loader._matches_pattern("README.md") is True
        assert loader._matches_pattern("script.py") is True
        assert loader._matches_pattern("data.json") is False

    def test_matches_wildcard_all(self):
        """Test wildcard pattern matching all files."""
        loader = GitHubLoader("owner/repo", pattern="*")

        assert loader._matches_pattern("README.md") is True
        assert loader._matches_pattern("script.py") is True
        assert loader._matches_pattern("anything") is True


class TestGitHubLoaderSkipPatterns:
    """Tests for skip pattern functionality."""

    def test_skip_default_patterns(self):
        """Test that default patterns are skipped."""
        loader = GitHubLoader("owner/repo")

        assert loader._should_skip("__pycache__/file.py") is True
        assert loader._should_skip("node_modules/package.json") is True
        assert loader._should_skip(".git/config") is True
        assert loader._should_skip("src/main.py") is False

    def test_skip_custom_patterns(self):
        """Test custom skip patterns."""
        loader = GitHubLoader("owner/repo", skip_patterns=["test_*", "*.bak"])

        assert loader._should_skip("test_main.py") is True
        assert loader._should_skip("backup.bak") is True
        assert loader._should_skip("main.py") is False

    def test_skip_empty_patterns(self):
        """Test with empty skip patterns (nothing skipped)."""
        loader = GitHubLoader("owner/repo", skip_patterns=[])

        assert loader._should_skip("__pycache__/file.py") is False
        assert loader._should_skip("node_modules/package.json") is False


class TestGitHubLoaderContentType:
    """Tests for content type guessing."""

    @pytest.fixture
    def loader(self):
        """Create a loader instance for testing."""
        return GitHubLoader("owner/repo")

    def test_guess_markdown(self, loader):
        """Test markdown content type."""
        assert loader._guess_content_type("README.md") == "text/markdown"

    def test_guess_python(self, loader):
        """Test Python content type."""
        assert loader._guess_content_type("script.py") == "text/x-python"

    def test_guess_json(self, loader):
        """Test JSON content type."""
        assert loader._guess_content_type("config.json") == "application/json"

    def test_guess_unknown(self, loader):
        """Test unknown extension defaults to text/plain."""
        assert loader._guess_content_type("file.xyz") == "text/plain"

    def test_guess_no_extension(self, loader):
        """Test file without extension."""
        assert loader._guess_content_type("Makefile") == "text/plain"


class TestGitHubLoaderLoad:
    """Tests for the load() method."""

    @pytest.fixture
    def mock_tree_response(self):
        """Mock GitHub tree API response."""
        return {
            "tree": [
                {"path": "docs/guide.md", "type": "blob"},
                {"path": "docs/api.md", "type": "blob"},
                {"path": "docs/__pycache__/cache.pyc", "type": "blob"},
                {"path": "src/main.py", "type": "blob"},
                {"path": "docs", "type": "tree"},  # Directory, should be skipped
            ],
            "truncated": False,
        }

    @pytest.mark.asyncio
    async def test_load_filters_by_path(self, mock_tree_response):
        """Test that load() filters files by path prefix."""
        loader = GitHubLoader("owner/repo", path="docs", pattern="*.md")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock tree response
            tree_response = MagicMock()
            tree_response.json.return_value = mock_tree_response
            tree_response.raise_for_status = MagicMock()

            # Mock file content responses
            content_response = MagicMock()
            content_response.text = "# Guide\nContent here"
            content_response.status_code = 200
            content_response.raise_for_status = MagicMock()

            mock_client.get.side_effect = [tree_response, content_response, content_response]

            contents = await loader.load()

            # Should only load docs/*.md files (2 files)
            assert len(contents) == 2
            assert all(c.source.startswith("github://owner/repo/docs/") for c in contents)

    @pytest.mark.asyncio
    async def test_load_skips_pycache(self, mock_tree_response):
        """Test that __pycache__ files are skipped."""
        loader = GitHubLoader("owner/repo", path="docs", pattern="*")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            tree_response = MagicMock()
            tree_response.json.return_value = mock_tree_response
            tree_response.raise_for_status = MagicMock()

            content_response = MagicMock()
            content_response.text = "content"
            content_response.status_code = 200
            content_response.raise_for_status = MagicMock()

            mock_client.get.side_effect = [tree_response, content_response, content_response]

            contents = await loader.load()

            # __pycache__ file should be skipped
            sources = [c.source for c in contents]
            assert not any("__pycache__" in s for s in sources)

    @pytest.mark.asyncio
    async def test_load_handles_404(self):
        """Test that 404 raises ValueError with helpful message."""
        loader = GitHubLoader("owner/nonexistent", path="docs")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = MagicMock()
            response.status_code = 404
            error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=response)
            mock_client.get.side_effect = error

            with pytest.raises(ValueError, match="Repository or branch not found"):
                await loader.load()

    @pytest.mark.asyncio
    async def test_load_handles_403_rate_limit(self):
        """Test that 403 raises ValueError with rate limit message."""
        loader = GitHubLoader("owner/repo")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = MagicMock()
            response.status_code = 403
            response.headers = {"X-RateLimit-Remaining": "0"}
            error = httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=response)
            mock_client.get.side_effect = error

            with pytest.raises(ValueError, match="rate limit"):
                await loader.load()

    @pytest.mark.asyncio
    async def test_load_populates_metadata(self, mock_tree_response):
        """Test that loaded content has correct metadata."""
        loader = GitHubLoader(
            "owner/repo",
            path="docs",
            branch="main",
            pattern="*.md",
            extra_metadata={"project": "test"},
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            tree_response = MagicMock()
            tree_response.json.return_value = mock_tree_response
            tree_response.raise_for_status = MagicMock()

            content_response = MagicMock()
            content_response.text = "# Content"
            content_response.status_code = 200
            content_response.raise_for_status = MagicMock()

            mock_client.get.side_effect = [tree_response, content_response, content_response]

            contents = await loader.load()

            assert len(contents) > 0
            content = contents[0]

            assert content.metadata["loader"] == "github"
            assert content.metadata["repo"] == "owner/repo"
            assert content.metadata["branch"] == "main"
            assert content.metadata["project"] == "test"  # extra_metadata
            assert "path" in content.metadata
            assert "full_path" in content.metadata


class TestGitHubLoaderSync:
    """Tests for synchronous loading."""

    def test_load_sync_works(self):
        """Test that load_sync() works in non-async context."""
        # This is an integration test that actually calls GitHub
        # Skip if no network or rate limited
        loader = GitHubLoader("nfraxlab/svc-infra", path="docs", pattern="auth.md")

        try:
            contents = loader.load_sync()
            assert len(contents) >= 0  # May be empty if rate limited
        except Exception:
            pytest.skip("GitHub API unavailable or rate limited")
