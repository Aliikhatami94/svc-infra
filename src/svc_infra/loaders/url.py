"""URL content loader.

Load content from URLs with automatic HTML text extraction.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from .base import BaseLoader, ErrorStrategy
from .models import LoadedContent

logger = logging.getLogger(__name__)


class URLLoader(BaseLoader):
    """Load content from one or more URLs.

    Fetches content from URLs and optionally extracts readable text from HTML.
    Supports redirects, custom headers, and batch loading.

    Args:
        urls: Single URL or list of URLs to load.
        headers: Optional HTTP headers to send with requests.
        extract_text: If True (default), extract readable text from HTML pages.
            Raw HTML is returned if False or if content is not HTML.
        follow_redirects: Follow HTTP redirects (default: True).
        timeout: Request timeout in seconds (default: 30).
        extra_metadata: Additional metadata to attach to all loaded content.
        on_error: How to handle errors ("skip" or "raise"). Default: "skip"

    Example:
        >>> # Load single URL
        >>> loader = URLLoader("https://example.com/docs/guide.md")
        >>> contents = await loader.load()
        >>> print(contents[0].content[:100])
        >>>
        >>> # Load multiple URLs
        >>> loader = URLLoader([
        ...     "https://example.com/page1",
        ...     "https://example.com/page2",
        ... ])
        >>> contents = await loader.load()
        >>>
        >>> # Disable HTML text extraction
        >>> loader = URLLoader("https://example.com", extract_text=False)
        >>> contents = await loader.load()  # Returns raw HTML
        >>>
        >>> # With custom headers (e.g., for APIs)
        >>> loader = URLLoader(
        ...     "https://api.example.com/docs",
        ...     headers={"Authorization": "Bearer token123"},
        ... )
        >>> contents = await loader.load()

    Note:
        - HTML text extraction removes scripts, styles, nav, footer, etc.
        - If BeautifulSoup is not installed, falls back to basic regex extraction
        - Content type is detected from HTTP headers
    """

    def __init__(
        self,
        urls: str | list[str],
        headers: dict[str, str] | None = None,
        extract_text: bool = True,
        follow_redirects: bool = True,
        timeout: float = 30.0,
        extra_metadata: dict[str, Any] | None = None,
        on_error: ErrorStrategy = "skip",
    ) -> None:
        """Initialize the URL loader.

        Args:
            urls: Single URL or list of URLs
            headers: HTTP headers to send
            extract_text: Extract text from HTML (default: True)
            follow_redirects: Follow redirects (default: True)
            timeout: Request timeout in seconds
            extra_metadata: Additional metadata for all content
            on_error: Error handling strategy
        """
        super().__init__(on_error=on_error)

        # Normalize urls to list
        self.urls = [urls] if isinstance(urls, str) else list(urls)
        self.headers = headers or {}
        self.extract_text = extract_text
        self.follow_redirects = follow_redirects
        self.timeout = timeout
        self.extra_metadata = extra_metadata or {}

        # Validate URLs
        for url in self.urls:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL: {url!r}. URLs must start with http:// or https://")

    async def load(self) -> list[LoadedContent]:
        """Load content from all URLs.

        Returns:
            List of LoadedContent objects for each successfully loaded URL.

        Raises:
            httpx.HTTPError: If request fails and on_error="raise".
        """
        contents: list[LoadedContent] = []

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=self.follow_redirects,
        ) as client:
            for url in self.urls:
                try:
                    logger.debug(f"Fetching: {url}")
                    resp = await client.get(url, headers=self.headers)
                    resp.raise_for_status()

                    content_type = resp.headers.get("content-type", "")
                    raw_content = resp.text

                    # Extract text from HTML if requested
                    if self.extract_text and "text/html" in content_type:
                        content = self._extract_text_from_html(raw_content)
                    else:
                        content = raw_content

                    # Parse content type (remove charset etc.)
                    mime_type = content_type.split(";")[0].strip() if content_type else None

                    loaded = LoadedContent(
                        content=content,
                        source=url,
                        content_type=mime_type,
                        metadata={
                            "loader": "url",
                            "url": url,
                            "status_code": resp.status_code,
                            "final_url": str(resp.url),  # After redirects
                            **self.extra_metadata,
                        },
                    )
                    contents.append(loaded)
                    logger.debug(f"Loaded: {url} ({len(content)} chars)")

                except httpx.HTTPStatusError as e:
                    msg = f"HTTP {e.response.status_code} for {url}"
                    if self.on_error == "raise":
                        raise RuntimeError(msg) from e
                    logger.warning(msg)

                except httpx.RequestError as e:
                    msg = f"Request failed for {url}: {e}"
                    if self.on_error == "raise":
                        raise RuntimeError(msg) from e
                    logger.warning(msg)

        return contents

    @staticmethod
    def _extract_text_from_html(html: str) -> str:
        """Extract readable text from HTML content.

        Tries to use BeautifulSoup if available, falls back to regex.

        Args:
            html: Raw HTML content

        Returns:
            Extracted text with scripts, styles, and navigation removed.
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Remove non-content elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()

            # Get text with newlines preserved
            text = soup.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()

        except ImportError:
            # Fallback: basic regex-based extraction
            logger.debug("BeautifulSoup not installed, using regex fallback")

            # Remove script and style blocks
            text = re.sub(
                r"<script[^>]*>.*?</script>",
                "",
                html,
                flags=re.DOTALL | re.IGNORECASE,
            )
            text = re.sub(
                r"<style[^>]*>.*?</style>",
                "",
                text,
                flags=re.DOTALL | re.IGNORECASE,
            )

            # Remove all HTML tags
            text = re.sub(r"<[^>]+>", " ", text)

            # Decode common HTML entities
            text = text.replace("&nbsp;", " ")
            text = text.replace("&amp;", "&")
            text = text.replace("&lt;", "<")
            text = text.replace("&gt;", ">")
            text = text.replace("&quot;", '"')
            text = text.replace("&#39;", "'")

            # Clean up whitespace
            text = " ".join(text.split())
            return text.strip()

    def __repr__(self) -> str:
        """Return string representation."""
        if len(self.urls) == 1:
            return f"URLLoader({self.urls[0]!r})"
        return f"URLLoader([{len(self.urls)} URLs])"
