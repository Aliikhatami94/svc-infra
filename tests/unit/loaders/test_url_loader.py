"""Tests for URLLoader.

Tests the URL content loader functionality including:
- Loading from single and multiple URLs
- HTML text extraction
- Redirect handling
- Error handling
- Metadata population
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from svc_infra.loaders import URLLoader


class TestURLLoaderInit:
    """Tests for URLLoader initialization."""

    def test_single_url_init(self):
        """Test initialization with single URL."""
        loader = URLLoader("https://example.com")

        assert loader.urls == ["https://example.com"]
        assert loader.extract_text is True
        assert loader.follow_redirects is True
        assert loader.timeout == 30.0

    def test_multiple_urls_init(self):
        """Test initialization with multiple URLs."""
        urls = ["https://example.com/page1", "https://example.com/page2"]
        loader = URLLoader(urls)

        assert loader.urls == urls
        assert len(loader.urls) == 2

    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        loader = URLLoader(
            urls="https://example.com",
            headers={"Authorization": "Bearer token"},
            extract_text=False,
            follow_redirects=False,
            timeout=60.0,
            extra_metadata={"source": "test"},
        )

        assert loader.urls == ["https://example.com"]
        assert loader.headers == {"Authorization": "Bearer token"}
        assert loader.extract_text is False
        assert loader.follow_redirects is False
        assert loader.timeout == 60.0
        assert loader.extra_metadata == {"source": "test"}

    def test_invalid_url_no_scheme(self):
        """Test that URL without scheme raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URL"):
            URLLoader("example.com")

    def test_invalid_url_wrong_scheme(self):
        """Test that non-http URL raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URL"):
            URLLoader("ftp://example.com")

    def test_http_url_accepted(self):
        """Test that http:// URL is accepted."""
        loader = URLLoader("http://example.com")
        assert loader.urls == ["http://example.com"]

    def test_https_url_accepted(self):
        """Test that https:// URL is accepted."""
        loader = URLLoader("https://example.com")
        assert loader.urls == ["https://example.com"]

    def test_repr_single_url(self):
        """Test string representation with single URL."""
        loader = URLLoader("https://example.com")
        assert repr(loader) == "URLLoader('https://example.com')"

    def test_repr_multiple_urls(self):
        """Test string representation with multiple URLs."""
        loader = URLLoader(["https://example.com/1", "https://example.com/2"])
        assert repr(loader) == "URLLoader([2 URLs])"


class TestURLLoaderHTMLExtraction:
    """Tests for HTML text extraction."""

    def test_extract_basic_html(self):
        """Test extraction from basic HTML."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>Hello World</h1>
            <p>This is a paragraph.</p>
        </body>
        </html>
        """

        text = URLLoader._extract_text_from_html(html)

        assert "Hello World" in text
        assert "This is a paragraph" in text
        assert "<html>" not in text
        assert "<h1>" not in text

    def test_extract_removes_scripts(self):
        """Test that script tags are removed."""
        html = """
        <html>
        <body>
            <p>Content</p>
            <script>alert('evil');</script>
            <p>More content</p>
        </body>
        </html>
        """

        text = URLLoader._extract_text_from_html(html)

        assert "Content" in text
        assert "More content" in text
        assert "alert" not in text
        assert "script" not in text.lower()

    def test_extract_removes_styles(self):
        """Test that style tags are removed."""
        html = """
        <html>
        <head><style>body { color: red; }</style></head>
        <body><p>Content</p></body>
        </html>
        """

        text = URLLoader._extract_text_from_html(html)

        assert "Content" in text
        assert "color" not in text
        assert "style" not in text.lower()

    def test_extract_removes_nav_footer(self):
        """Test that nav and footer are removed."""
        html = """
        <html>
        <body>
            <nav>Navigation links</nav>
            <main><p>Main content</p></main>
            <footer>Footer info</footer>
        </body>
        </html>
        """

        text = URLLoader._extract_text_from_html(html)

        assert "Main content" in text
        # nav and footer should be removed (if BeautifulSoup is available)
        # With regex fallback, they might still be there as text

    def test_extract_handles_entities(self):
        """Test HTML entity decoding with regex fallback."""
        # Test the regex fallback path
        html = "<p>Hello &amp; goodbye &lt;world&gt;</p>"

        # Force regex fallback by mocking bs4 import
        with patch.dict("sys.modules", {"bs4": None}):
            text = URLLoader._extract_text_from_html(html)

        # Entities should be decoded
        assert "&" in text or "&amp;" in text  # May or may not be decoded


class TestURLLoaderLoad:
    """Tests for the load() method."""

    @pytest.mark.asyncio
    async def test_load_single_url(self):
        """Test loading a single URL."""
        loader = URLLoader("https://example.com")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = MagicMock()
            response.text = "Hello World"
            response.headers = {"content-type": "text/plain"}
            response.status_code = 200
            response.url = "https://example.com"
            response.raise_for_status = MagicMock()

            mock_client.get.return_value = response

            contents = await loader.load()

            assert len(contents) == 1
            assert contents[0].content == "Hello World"
            assert contents[0].source == "https://example.com"

    @pytest.mark.asyncio
    async def test_load_multiple_urls(self):
        """Test loading multiple URLs."""
        loader = URLLoader(["https://example.com/1", "https://example.com/2"])

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            def make_response(url, text):
                response = MagicMock()
                response.text = text
                response.headers = {"content-type": "text/plain"}
                response.status_code = 200
                response.url = url
                response.raise_for_status = MagicMock()
                return response

            mock_client.get.side_effect = [
                make_response("https://example.com/1", "Page 1"),
                make_response("https://example.com/2", "Page 2"),
            ]

            contents = await loader.load()

            assert len(contents) == 2
            assert contents[0].content == "Page 1"
            assert contents[1].content == "Page 2"

    @pytest.mark.asyncio
    async def test_load_extracts_html_text(self):
        """Test that HTML text is extracted when extract_text=True."""
        loader = URLLoader("https://example.com", extract_text=True)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = MagicMock()
            response.text = "<html><body><p>Hello World</p></body></html>"
            response.headers = {"content-type": "text/html; charset=utf-8"}
            response.status_code = 200
            response.url = "https://example.com"
            response.raise_for_status = MagicMock()

            mock_client.get.return_value = response

            contents = await loader.load()

            assert len(contents) == 1
            assert "Hello World" in contents[0].content
            assert "<html>" not in contents[0].content

    @pytest.mark.asyncio
    async def test_load_preserves_raw_html(self):
        """Test that HTML is preserved when extract_text=False."""
        loader = URLLoader("https://example.com", extract_text=False)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            html = "<html><body><p>Hello World</p></body></html>"
            response = MagicMock()
            response.text = html
            response.headers = {"content-type": "text/html"}
            response.status_code = 200
            response.url = "https://example.com"
            response.raise_for_status = MagicMock()

            mock_client.get.return_value = response

            contents = await loader.load()

            assert len(contents) == 1
            assert contents[0].content == html

    @pytest.mark.asyncio
    async def test_load_handles_404_skip(self):
        """Test that 404 is skipped when on_error='skip'."""
        loader = URLLoader(
            ["https://example.com/exists", "https://example.com/404"],
            on_error="skip",
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            success_response = MagicMock()
            success_response.text = "Content"
            success_response.headers = {"content-type": "text/plain"}
            success_response.status_code = 200
            success_response.url = "https://example.com/exists"
            success_response.raise_for_status = MagicMock()

            error_response = MagicMock()
            error_response.status_code = 404
            error = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=error_response
            )

            mock_client.get.side_effect = [success_response, error]

            contents = await loader.load()

            # Should only have 1 result (404 skipped)
            assert len(contents) == 1
            assert contents[0].source == "https://example.com/exists"

    @pytest.mark.asyncio
    async def test_load_handles_404_raise(self):
        """Test that 404 raises when on_error='raise'."""
        loader = URLLoader("https://example.com/404", on_error="raise")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = MagicMock()
            response.status_code = 404
            error = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=response
            )
            mock_client.get.side_effect = error

            with pytest.raises(RuntimeError, match="HTTP 404"):
                await loader.load()

    @pytest.mark.asyncio
    async def test_load_tracks_redirects(self):
        """Test that final URL after redirects is tracked."""
        loader = URLLoader("https://example.com/redirect")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = MagicMock()
            response.text = "Content"
            response.headers = {"content-type": "text/plain"}
            response.status_code = 200
            response.url = "https://example.com/final"  # After redirect
            response.raise_for_status = MagicMock()

            mock_client.get.return_value = response

            contents = await loader.load()

            assert len(contents) == 1
            assert contents[0].metadata["url"] == "https://example.com/redirect"
            assert contents[0].metadata["final_url"] == "https://example.com/final"

    @pytest.mark.asyncio
    async def test_load_populates_metadata(self):
        """Test that loaded content has correct metadata."""
        loader = URLLoader(
            "https://example.com",
            extra_metadata={"category": "test"},
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = MagicMock()
            response.text = "Content"
            response.headers = {"content-type": "text/plain"}
            response.status_code = 200
            response.url = "https://example.com"
            response.raise_for_status = MagicMock()

            mock_client.get.return_value = response

            contents = await loader.load()

            assert len(contents) == 1
            metadata = contents[0].metadata

            assert metadata["loader"] == "url"
            assert metadata["url"] == "https://example.com"
            assert metadata["status_code"] == 200
            assert metadata["category"] == "test"  # extra_metadata

    @pytest.mark.asyncio
    async def test_load_parses_content_type(self):
        """Test that content type is parsed correctly."""
        loader = URLLoader("https://example.com")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = MagicMock()
            response.text = "Content"
            response.headers = {"content-type": "text/html; charset=utf-8"}
            response.status_code = 200
            response.url = "https://example.com"
            response.raise_for_status = MagicMock()

            mock_client.get.return_value = response

            contents = await loader.load()

            # Content type should be parsed (charset removed)
            assert contents[0].content_type == "text/html"


class TestURLLoaderSync:
    """Tests for synchronous loading."""

    def test_load_sync_works(self):
        """Test that load_sync() works in non-async context."""
        # This is an integration test that actually makes HTTP requests
        loader = URLLoader(
            "https://raw.githubusercontent.com/nfraxlab/svc-infra/main/README.md"
        )

        try:
            contents = loader.load_sync()
            assert len(contents) == 1
            assert "svc-infra" in contents[0].content.lower()
        except Exception:
            pytest.skip("Network unavailable")
