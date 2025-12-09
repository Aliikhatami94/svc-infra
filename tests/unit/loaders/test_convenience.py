"""Tests for convenience functions and shared functionality.

Tests the module-level convenience functions and LoadedContent model.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from svc_infra.loaders import (
    BaseLoader,
    GitHubLoader,
    LoadedContent,
    URLLoader,
    load_github,
    load_github_sync,
    load_url,
    load_url_sync,
)


class TestLoadedContent:
    """Tests for LoadedContent dataclass."""

    def test_basic_creation(self):
        """Test basic LoadedContent creation."""
        content = LoadedContent(
            content="Hello World",
            source="https://example.com",
        )

        assert content.content == "Hello World"
        assert content.source == "https://example.com"
        assert content.metadata == {"source": "https://example.com"}
        assert content.content_type is None
        assert content.encoding == "utf-8"

    def test_creation_with_metadata(self):
        """Test LoadedContent with custom metadata."""
        content = LoadedContent(
            content="Hello",
            source="test://source",
            metadata={"key": "value"},
        )

        assert content.metadata["key"] == "value"
        assert content.metadata["source"] == "test://source"

    def test_source_added_to_metadata(self):
        """Test that source is automatically added to metadata."""
        content = LoadedContent(
            content="Hello",
            source="test://source",
            metadata={},
        )

        assert "source" in content.metadata
        assert content.metadata["source"] == "test://source"

    def test_source_not_overwritten_in_metadata(self):
        """Test that existing source in metadata is not overwritten."""
        content = LoadedContent(
            content="Hello",
            source="test://new",
            metadata={"source": "test://existing"},
        )

        # Existing source should be preserved
        assert content.metadata["source"] == "test://existing"

    def test_to_tuple(self):
        """Test conversion to (content, metadata) tuple."""
        content = LoadedContent(
            content="Hello",
            source="test://source",
            metadata={"key": "value"},
        )

        text, meta = content.to_tuple()

        assert text == "Hello"
        assert meta["key"] == "value"
        assert meta["source"] == "test://source"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_load_github_creates_loader(self):
        """Test that load_github creates GitHubLoader and calls load."""
        with patch.object(GitHubLoader, "load", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = [LoadedContent(content="test", source="github://test")]

            contents = await load_github("owner/repo", path="docs", pattern="*.md")

            assert len(contents) == 1
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_url_creates_loader(self):
        """Test that load_url creates URLLoader and calls load."""
        with patch.object(URLLoader, "load", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = [LoadedContent(content="test", source="https://example.com")]

            contents = await load_url("https://example.com")

            assert len(contents) == 1
            mock_load.assert_called_once()

    def test_load_github_sync_creates_loader(self):
        """Test that load_github_sync creates GitHubLoader and calls load_sync."""
        with patch.object(GitHubLoader, "load_sync") as mock_load:
            mock_load.return_value = [LoadedContent(content="test", source="github://test")]

            contents = load_github_sync("owner/repo", path="docs")

            assert len(contents) == 1
            mock_load.assert_called_once()

    def test_load_url_sync_creates_loader(self):
        """Test that load_url_sync creates URLLoader and calls load_sync."""
        with patch.object(URLLoader, "load_sync") as mock_load:
            mock_load.return_value = [LoadedContent(content="test", source="https://example.com")]

            contents = load_url_sync("https://example.com")

            assert len(contents) == 1
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_github_passes_kwargs(self):
        """Test that load_github passes extra kwargs to loader."""
        with patch.object(GitHubLoader, "__init__", return_value=None) as mock_init:
            with patch.object(GitHubLoader, "load", new_callable=AsyncMock) as mock_load:
                mock_load.return_value = []

                await load_github(
                    "owner/repo",
                    path="src",
                    branch="develop",
                    pattern="*.py",
                    token="test-token",
                    extra_metadata={"key": "value"},
                )

                mock_init.assert_called_once_with(
                    "owner/repo",
                    path="src",
                    branch="develop",
                    pattern="*.py",
                    token="test-token",
                    extra_metadata={"key": "value"},
                )

    @pytest.mark.asyncio
    async def test_load_url_passes_kwargs(self):
        """Test that load_url passes extra kwargs to loader."""
        with patch.object(URLLoader, "__init__", return_value=None) as mock_init:
            with patch.object(URLLoader, "load", new_callable=AsyncMock) as mock_load:
                mock_load.return_value = []

                await load_url(
                    "https://example.com",
                    headers={"Auth": "token"},
                    extract_text=False,
                    timeout=60.0,
                )

                mock_init.assert_called_once_with(
                    "https://example.com",
                    headers={"Auth": "token"},
                    extract_text=False,
                    timeout=60.0,
                )


class TestBaseLoader:
    """Tests for BaseLoader abstract class."""

    def test_cannot_instantiate_directly(self):
        """Test that BaseLoader cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseLoader()

    def test_subclass_must_implement_load(self):
        """Test that subclass must implement load method."""

        class IncompleteLoader(BaseLoader):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteLoader()

    def test_subclass_with_load_works(self):
        """Test that subclass with load method can be instantiated."""

        class CompleteLoader(BaseLoader):
            async def load(self):
                return []

        loader = CompleteLoader()
        assert isinstance(loader, BaseLoader)


class TestModuleExports:
    """Tests for module exports."""

    def test_all_classes_exported(self):
        """Test that all expected classes are exported."""
        from svc_infra.loaders import BaseLoader, GitHubLoader, LoadedContent, URLLoader

        assert BaseLoader is not None
        assert GitHubLoader is not None
        assert URLLoader is not None
        assert LoadedContent is not None

    def test_all_functions_exported(self):
        """Test that all expected functions are exported."""
        from svc_infra.loaders import load_github, load_github_sync, load_url, load_url_sync

        assert callable(load_github)
        assert callable(load_github_sync)
        assert callable(load_url)
        assert callable(load_url_sync)

    def test_compatibility_exports(self):
        """Test that compatibility exports are available."""
        from svc_infra.loaders import LoadedDocument, to_loaded_documents

        assert LoadedDocument is not None
        assert callable(to_loaded_documents)
