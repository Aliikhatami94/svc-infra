# Content Loaders

Load content from remote sources for RAG, search indexing, and document processing.

## Overview

The `svc_infra.loaders` module provides async-first content loaders for fetching from various remote sources. All loaders return a consistent `LoadedContent` format that integrates seamlessly with ai-infra's `Retriever`.

### Key Features

- **Async-first** with sync wrappers for scripts and notebooks
- **Consistent output format** (`LoadedContent`) across all loaders
- **ai-infra compatible** - works directly with `Retriever.add_text()`
- **Smart defaults** - skip patterns, content type detection, error handling
- **Extensible** - easy to create custom loaders by extending `BaseLoader`

## Quick Start

### Installation

Content loaders are included in the base `svc-infra` package:

```bash
pip install svc-infra
```

### Basic Usage

```python
from svc_infra.loaders import GitHubLoader, URLLoader, load_github, load_url

# Load from GitHub
loader = GitHubLoader("nfraxlab/svc-infra", path="docs", pattern="*.md")
contents = await loader.load()

# Load from URLs
loader = URLLoader("https://example.com/guide.md")
contents = await loader.load()

# Or use convenience functions
contents = await load_github("nfraxlab/svc-infra", path="docs")
contents = await load_url("https://example.com/guide.md")
```

### Sync Usage (Scripts/Notebooks)

```python
from svc_infra.loaders import load_github_sync, load_url_sync

# No async/await needed!
contents = load_github_sync("nfraxlab/svc-infra", path="docs")
contents = load_url_sync("https://example.com/guide.md")
```

### With ai-infra Retriever

```python
from ai_infra import Retriever
from svc_infra.loaders import load_github

retriever = Retriever()

# Load and embed documentation from multiple repos
for pkg in ["svc-infra", "ai-infra", "fin-infra"]:
    contents = await load_github(f"nfraxlab/{pkg}", path="docs")
    for c in contents:
        retriever.add_text(c.content, metadata=c.metadata)

# Search across all docs
results = retriever.search("authentication")
```

## GitHubLoader

Load files from GitHub repositories.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo` | `str` | required | Repository in "owner/repo" format |
| `path` | `str` | `""` | Path within repo (empty = root) |
| `branch` | `str` | `"main"` | Branch name |
| `pattern` | `str` | `"*.md"` | Glob pattern for files to include |
| `token` | `str` | `None` | GitHub token (falls back to `GITHUB_TOKEN` env) |
| `recursive` | `bool` | `True` | Search subdirectories |
| `skip_patterns` | `list[str]` | See below | Patterns to exclude |
| `extra_metadata` | `dict` | `{}` | Additional metadata for all content |
| `on_error` | `str` | `"skip"` | Error handling: `"skip"` or `"raise"` |

### Default Skip Patterns

```python
[
    "__pycache__", "*.pyc", "*.pyo", ".git", ".github",
    "node_modules", "*.lock", ".env*", ".DS_Store",
    "*.egg-info", "dist", "build", "*.min.js", "*.min.css",
]
```

### Examples

```python
from svc_infra.loaders import GitHubLoader

# Load all markdown from docs/
loader = GitHubLoader("nfraxlab/svc-infra", path="docs")
contents = await loader.load()

# Load Python files, excluding tests
loader = GitHubLoader(
    "nfraxlab/svc-infra",
    path="src",
    pattern="*.py",
    skip_patterns=["test_*", "*_test.py"],
)
contents = await loader.load()

# Multiple patterns (separate with |)
loader = GitHubLoader(
    "nfraxlab/svc-infra",
    path="examples",
    pattern="*.py|*.md|*.yaml",
)
contents = await loader.load()

# Private repo with token
loader = GitHubLoader(
    "myorg/private-repo",
    token="ghp_xxxx",  # or set GITHUB_TOKEN env var
)
contents = await loader.load()

# Add custom metadata to all content
loader = GitHubLoader(
    "nfraxlab/svc-infra",
    path="docs",
    extra_metadata={"package": "svc-infra", "type": "documentation"},
)
contents = await loader.load()
```

### Metadata Output

Each `LoadedContent` from GitHubLoader includes:

```python
{
    "loader": "github",
    "repo": "nfraxlab/svc-infra",
    "branch": "main",
    "path": "auth.md",           # Relative to specified path
    "full_path": "docs/auth.md", # Full path in repo
    "source": "github://nfraxlab/svc-infra/docs/auth.md",
    # Plus any extra_metadata you provided
}
```

## URLLoader

Load content from URLs with automatic HTML text extraction.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `urls` | `str \| list[str]` | required | URL(s) to load |
| `headers` | `dict[str, str]` | `{}` | HTTP headers to send |
| `extract_text` | `bool` | `True` | Extract text from HTML |
| `follow_redirects` | `bool` | `True` | Follow HTTP redirects |
| `timeout` | `float` | `30.0` | Request timeout in seconds |
| `extra_metadata` | `dict` | `{}` | Additional metadata |
| `on_error` | `str` | `"skip"` | Error handling: `"skip"` or `"raise"` |

### Examples

```python
from svc_infra.loaders import URLLoader

# Load single URL
loader = URLLoader("https://example.com/docs/guide.md")
contents = await loader.load()

# Load multiple URLs
loader = URLLoader([
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3",
])
contents = await loader.load()

# Keep raw HTML (don't extract text)
loader = URLLoader(
    "https://example.com",
    extract_text=False,
)
contents = await loader.load()

# With custom headers (e.g., for APIs)
loader = URLLoader(
    "https://api.example.com/docs",
    headers={"Authorization": "Bearer token123"},
)
contents = await loader.load()

# Fail on errors instead of skipping
loader = URLLoader(
    "https://example.com/must-exist.md",
    on_error="raise",
)
contents = await loader.load()  # Raises RuntimeError if 404
```

### HTML Text Extraction

When `extract_text=True` (default), URLLoader automatically:

- Removes `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>` tags
- Extracts readable text content
- Cleans up excessive whitespace

Uses BeautifulSoup if installed, falls back to regex otherwise.

### Metadata Output

Each `LoadedContent` from URLLoader includes:

```python
{
    "loader": "url",
    "url": "https://example.com/page",      # Original URL
    "final_url": "https://example.com/page", # After redirects
    "status_code": 200,
    "source": "https://example.com/page",
    # Plus any extra_metadata you provided
}
```

## LoadedContent

The standard output format for all loaders.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | The loaded text content |
| `source` | `str` | Source identifier (URL, GitHub URI, etc.) |
| `content_type` | `str \| None` | MIME type (e.g., "text/markdown") |
| `metadata` | `dict` | All metadata (source auto-added) |
| `encoding` | `str` | Character encoding (default: "utf-8") |

### Methods

```python
# Convert to tuple for Retriever compatibility
text, metadata = content.to_tuple()

# Access properties
print(content.source)       # "github://owner/repo/docs/auth.md"
print(content.content_type) # "text/markdown"
print(content.metadata)     # {"repo": "owner/repo", "path": "auth.md", ...}
```

### Usage with ai-infra

```python
from ai_infra import Retriever
from svc_infra.loaders import GitHubLoader

retriever = Retriever()
loader = GitHubLoader("nfraxlab/svc-infra", path="docs")

for content in await loader.load():
    # Option 1: Direct use
    retriever.add_text(content.content, metadata=content.metadata)

    # Option 2: Using to_tuple()
    text, meta = content.to_tuple()
    retriever.add_text(text, metadata=meta)
```

## Convenience Functions

Quick one-liner functions for common use cases.

### Async Functions

```python
from svc_infra.loaders import load_github, load_url

# Load from GitHub
contents = await load_github(
    "nfraxlab/svc-infra",
    path="docs",
    pattern="*.md",
)

# Load from URL(s)
contents = await load_url("https://example.com/guide.md")
contents = await load_url([
    "https://example.com/page1",
    "https://example.com/page2",
])
```

### Sync Functions

```python
from svc_infra.loaders import load_github_sync, load_url_sync

# For scripts, notebooks, or non-async contexts
contents = load_github_sync("nfraxlab/svc-infra", path="docs")
contents = load_url_sync("https://example.com/guide.md")
```

## Creating Custom Loaders

Extend `BaseLoader` to create custom loaders:

```python
from svc_infra.loaders import BaseLoader, LoadedContent

class MyCustomLoader(BaseLoader):
    """Load content from a custom source."""

    def __init__(self, source_config, on_error="skip"):
        super().__init__(on_error=on_error)
        self.source_config = source_config

    async def load(self) -> list[LoadedContent]:
        contents = []

        # Your loading logic here
        for item in self._fetch_items():
            contents.append(LoadedContent(
                content=item["text"],
                source=f"custom://{item['id']}",
                content_type="text/plain",
                metadata={"id": item["id"]},
            ))

        return contents

# Use like any other loader
loader = MyCustomLoader(config)
contents = await loader.load()
contents = loader.load_sync()  # Inherited from BaseLoader
```

## Error Handling

All loaders support two error handling strategies:

### Skip (Default)

```python
loader = GitHubLoader("owner/repo", on_error="skip")
# Failed files are logged and skipped
# Returns partial results
```

### Raise

```python
loader = GitHubLoader("owner/repo", on_error="raise")
# Raises exception on first error
# ValueError for 404/403
# RuntimeError for other failures
```

## Rate Limits

### GitHub API

- **Unauthenticated**: 60 requests/hour
- **With token**: 5,000 requests/hour

Set `GITHUB_TOKEN` environment variable or pass `token` parameter for higher limits.

### HTTP Requests

URLLoader defaults to 30-second timeout. Adjust with `timeout` parameter.

## Best Practices

### 1. Use Extra Metadata for Multi-Source Indexing

```python
for pkg in ["svc-infra", "ai-infra", "fin-infra"]:
    contents = await load_github(
        f"nfraxlab/{pkg}",
        path="docs",
        extra_metadata={"package": pkg, "type": "docs"},
    )
    for c in contents:
        retriever.add_text(c.content, metadata=c.metadata)

# Later, filter by package
results = retriever.search("auth", filter={"package": "svc-infra"})
```

### 2. Use Specific Patterns

```python
# Good: specific patterns
loader = GitHubLoader("owner/repo", pattern="*.md")

# Better: exclude noise
loader = GitHubLoader(
    "owner/repo",
    pattern="*.py",
    skip_patterns=["test_*", "*_test.py", "conftest.py"],
)
```

### 3. Handle Large Repos

```python
# Load specific paths instead of entire repo
for path in ["docs", "examples", "src/core"]:
    contents = await load_github("owner/repo", path=path)
    # Process in batches
```

### 4. Use Sync Functions in Notebooks

```python
# In Jupyter notebooks, use sync versions
contents = load_github_sync("nfraxlab/svc-infra", path="docs")
```

## API Summary

### Classes

- `GitHubLoader` - Load from GitHub repositories
- `URLLoader` - Load from URLs
- `BaseLoader` - Abstract base class for custom loaders
- `LoadedContent` - Standard content container

### Functions

- `load_github()` - Async convenience function for GitHub
- `load_url()` - Async convenience function for URLs
- `load_github_sync()` - Sync convenience function for GitHub
- `load_url_sync()` - Sync convenience function for URLs

### All Exports

```python
from svc_infra.loaders import (
    # Classes
    BaseLoader,
    GitHubLoader,
    URLLoader,
    LoadedContent,
    # Async functions
    load_github,
    load_url,
    # Sync functions
    load_github_sync,
    load_url_sync,
)
```

---

## Additional Loaders

Beyond the built-in GitHubLoader and URLLoader, you can create custom loaders for various content sources. Here are examples for common platforms:

### ConfluenceLoader

Load content from Atlassian Confluence wikis:

```python
from svc_infra.loaders import BaseLoader, LoadedContent
import httpx
from typing import Literal

class ConfluenceLoader(BaseLoader):
    """Load content from Confluence spaces and pages.

    Args:
        base_url: Confluence base URL (e.g., "https://company.atlassian.net/wiki")
        space_key: Confluence space key to load from (e.g., "ENG")
        email: Atlassian account email
        api_token: Atlassian API token (from https://id.atlassian.com/manage-profile/security/api-tokens)
        page_ids: Specific page IDs to load (optional, loads all if not specified)
        include_children: Include child pages recursively
        include_attachments: Include page attachments
        on_error: Error handling strategy ("skip" or "raise")

    Example:
        >>> loader = ConfluenceLoader(
        ...     base_url="https://company.atlassian.net/wiki",
        ...     space_key="ENG",
        ...     email="user@company.com",
        ...     api_token=os.getenv("CONFLUENCE_API_TOKEN"),
        ... )
        >>> contents = await loader.load()
        >>> for content in contents:
        ...     print(f"{content.source}: {len(content.content)} chars")
    """

    def __init__(
        self,
        base_url: str,
        space_key: str,
        email: str,
        api_token: str,
        *,
        page_ids: list[str] | None = None,
        include_children: bool = True,
        include_attachments: bool = False,
        on_error: Literal["skip", "raise"] = "skip",
    ):
        super().__init__(on_error=on_error)
        self.base_url = base_url.rstrip("/")
        self.space_key = space_key
        self.page_ids = page_ids
        self.include_children = include_children
        self.include_attachments = include_attachments
        self._auth = (email, api_token)

    async def load(self) -> list[LoadedContent]:
        """Load content from Confluence."""
        contents = []

        async with httpx.AsyncClient(auth=self._auth, timeout=60.0) as client:
            # Get pages in space
            pages = await self._get_pages(client)

            for page in pages:
                try:
                    content = await self._load_page(client, page)
                    contents.append(content)

                    # Load attachments if requested
                    if self.include_attachments:
                        attachments = await self._load_attachments(client, page["id"])
                        contents.extend(attachments)

                except Exception as e:
                    if self.on_error == "raise":
                        raise
                    # Skip failed pages

        return contents

    async def _get_pages(self, client: httpx.AsyncClient) -> list[dict]:
        """Get pages from space or by IDs."""
        if self.page_ids:
            # Load specific pages
            pages = []
            for page_id in self.page_ids:
                resp = await client.get(
                    f"{self.base_url}/api/v2/pages/{page_id}",
                    params={"body-format": "storage"}
                )
                resp.raise_for_status()
                pages.append(resp.json())
            return pages

        # Load all pages in space
        pages = []
        url = f"{self.base_url}/api/v2/spaces/{self.space_key}/pages"
        params = {"limit": 100, "body-format": "storage"}

        while url:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            pages.extend(data.get("results", []))

            # Handle pagination
            url = data.get("_links", {}).get("next")
            params = {}  # Params included in next URL

        return pages

    async def _load_page(self, client: httpx.AsyncClient, page: dict) -> LoadedContent:
        """Load content from a single page."""
        page_id = page["id"]
        title = page["title"]

        # Get page body
        body_html = page.get("body", {}).get("storage", {}).get("value", "")

        # Convert HTML to plain text
        text = self._html_to_text(body_html)

        # Build source URI
        source = f"confluence://{self.space_key}/{page_id}"

        return LoadedContent(
            content=text,
            source=source,
            content_type="text/plain",
            metadata={
                "loader": "confluence",
                "space_key": self.space_key,
                "page_id": page_id,
                "title": title,
                "url": f"{self.base_url}/pages/{page_id}",
                "created_at": page.get("createdAt"),
                "updated_at": page.get("version", {}).get("createdAt"),
            }
        )

    async def _load_attachments(
        self,
        client: httpx.AsyncClient,
        page_id: str
    ) -> list[LoadedContent]:
        """Load text attachments from a page."""
        contents = []

        resp = await client.get(
            f"{self.base_url}/api/v2/pages/{page_id}/attachments"
        )
        resp.raise_for_status()

        for attachment in resp.json().get("results", []):
            # Only load text-based attachments
            media_type = attachment.get("mediaType", "")
            if not media_type.startswith("text/"):
                continue

            # Download attachment
            download_url = attachment.get("_links", {}).get("download")
            if download_url:
                file_resp = await client.get(f"{self.base_url}{download_url}")
                if file_resp.status_code == 200:
                    contents.append(LoadedContent(
                        content=file_resp.text,
                        source=f"confluence://{self.space_key}/{page_id}/attachments/{attachment['id']}",
                        content_type=media_type,
                        metadata={
                            "loader": "confluence",
                            "type": "attachment",
                            "page_id": page_id,
                            "filename": attachment.get("title"),
                        }
                    ))

        return contents

    def _html_to_text(self, html: str) -> str:
        """Convert Confluence HTML to plain text."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted elements
            for tag in soup.find_all(["script", "style", "ac:structured-macro"]):
                tag.decompose()

            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            # Fallback: basic HTML stripping
            import re
            text = re.sub(r"<[^>]+>", " ", html)
            return re.sub(r"\s+", " ", text).strip()
```

#### Confluence Usage Examples

```python
import os
from svc_infra.loaders import ConfluenceLoader

# Load entire space
loader = ConfluenceLoader(
    base_url="https://company.atlassian.net/wiki",
    space_key="ENG",
    email=os.getenv("CONFLUENCE_EMAIL"),
    api_token=os.getenv("CONFLUENCE_API_TOKEN"),
)
contents = await loader.load()

# Load specific pages
loader = ConfluenceLoader(
    base_url="https://company.atlassian.net/wiki",
    space_key="ENG",
    email=os.getenv("CONFLUENCE_EMAIL"),
    api_token=os.getenv("CONFLUENCE_API_TOKEN"),
    page_ids=["123456", "789012"],
)
contents = await loader.load()

# Index for RAG
from ai_infra import Retriever

retriever = Retriever()
for content in contents:
    retriever.add_text(
        content.content,
        metadata={
            **content.metadata,
            "source_type": "confluence"
        }
    )
```

### NotionLoader

Load content from Notion workspaces:

```python
from svc_infra.loaders import BaseLoader, LoadedContent
import httpx
from typing import Literal

class NotionLoader(BaseLoader):
    """Load content from Notion pages and databases.

    Args:
        api_token: Notion integration token (from https://www.notion.so/my-integrations)
        database_ids: List of database IDs to load
        page_ids: List of page IDs to load
        include_children: Include child blocks/pages
        on_error: Error handling strategy ("skip" or "raise")

    Note:
        The Notion integration must have access to the pages/databases.
        Share pages with the integration in Notion's "Share" menu.

    Example:
        >>> loader = NotionLoader(
        ...     api_token=os.getenv("NOTION_API_TOKEN"),
        ...     database_ids=["abc123..."],
        ... )
        >>> contents = await loader.load()
    """

    NOTION_API_VERSION = "2022-06-28"
    BASE_URL = "https://api.notion.com/v1"

    def __init__(
        self,
        api_token: str,
        *,
        database_ids: list[str] | None = None,
        page_ids: list[str] | None = None,
        include_children: bool = True,
        on_error: Literal["skip", "raise"] = "skip",
    ):
        super().__init__(on_error=on_error)
        self.api_token = api_token
        self.database_ids = database_ids or []
        self.page_ids = page_ids or []
        self.include_children = include_children

        if not self.database_ids and not self.page_ids:
            raise ValueError("Must provide database_ids or page_ids")

    async def load(self) -> list[LoadedContent]:
        """Load content from Notion."""
        contents = []

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Notion-Version": self.NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
            # Load from databases
            for db_id in self.database_ids:
                try:
                    db_contents = await self._load_database(client, db_id)
                    contents.extend(db_contents)
                except Exception as e:
                    if self.on_error == "raise":
                        raise

            # Load specific pages
            for page_id in self.page_ids:
                try:
                    page_content = await self._load_page(client, page_id)
                    contents.append(page_content)
                except Exception as e:
                    if self.on_error == "raise":
                        raise

        return contents

    async def _load_database(
        self,
        client: httpx.AsyncClient,
        database_id: str
    ) -> list[LoadedContent]:
        """Load all pages from a database."""
        contents = []
        has_more = True
        start_cursor = None

        while has_more:
            payload = {"page_size": 100}
            if start_cursor:
                payload["start_cursor"] = start_cursor

            resp = await client.post(
                f"{self.BASE_URL}/databases/{database_id}/query",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("results", []):
                try:
                    content = await self._load_page(client, page["id"])
                    contents.append(content)
                except Exception:
                    if self.on_error == "raise":
                        raise

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        return contents

    async def _load_page(
        self,
        client: httpx.AsyncClient,
        page_id: str
    ) -> LoadedContent:
        """Load content from a single page."""
        # Get page metadata
        page_resp = await client.get(f"{self.BASE_URL}/pages/{page_id}")
        page_resp.raise_for_status()
        page_data = page_resp.json()

        # Get page title
        title = self._extract_title(page_data)

        # Get page blocks (content)
        blocks = await self._get_blocks(client, page_id)
        text = self._blocks_to_text(blocks)

        return LoadedContent(
            content=text,
            source=f"notion://{page_id}",
            content_type="text/plain",
            metadata={
                "loader": "notion",
                "page_id": page_id,
                "title": title,
                "url": page_data.get("url"),
                "created_time": page_data.get("created_time"),
                "last_edited_time": page_data.get("last_edited_time"),
            }
        )

    async def _get_blocks(
        self,
        client: httpx.AsyncClient,
        block_id: str
    ) -> list[dict]:
        """Get all blocks from a page or block."""
        blocks = []
        has_more = True
        start_cursor = None

        while has_more:
            params = {"page_size": 100}
            if start_cursor:
                params["start_cursor"] = start_cursor

            resp = await client.get(
                f"{self.BASE_URL}/blocks/{block_id}/children",
                params=params
            )
            resp.raise_for_status()
            data = resp.json()

            for block in data.get("results", []):
                blocks.append(block)

                # Recursively get children if requested
                if self.include_children and block.get("has_children"):
                    child_blocks = await self._get_blocks(client, block["id"])
                    blocks.extend(child_blocks)

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        return blocks

    def _extract_title(self, page_data: dict) -> str:
        """Extract page title from properties."""
        properties = page_data.get("properties", {})

        # Check for title property
        for prop in properties.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_parts)

        return "Untitled"

    def _blocks_to_text(self, blocks: list[dict]) -> str:
        """Convert Notion blocks to plain text."""
        lines = []

        for block in blocks:
            block_type = block.get("type")
            block_content = block.get(block_type, {})

            # Extract rich_text content
            rich_text = block_content.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)

            # Format based on block type
            if block_type == "heading_1":
                lines.append(f"# {text}")
            elif block_type == "heading_2":
                lines.append(f"## {text}")
            elif block_type == "heading_3":
                lines.append(f"### {text}")
            elif block_type == "bulleted_list_item":
                lines.append(f"• {text}")
            elif block_type == "numbered_list_item":
                lines.append(f"1. {text}")
            elif block_type == "to_do":
                checked = "x" if block_content.get("checked") else " "
                lines.append(f"[{checked}] {text}")
            elif block_type == "code":
                language = block_content.get("language", "")
                lines.append(f"```{language}\n{text}\n```")
            elif block_type == "quote":
                lines.append(f"> {text}")
            elif block_type == "callout":
                emoji = block_content.get("icon", {}).get("emoji", "💡")
                lines.append(f"{emoji} {text}")
            elif block_type == "divider":
                lines.append("---")
            elif text:
                lines.append(text)

        return "\n".join(lines)
```

#### Notion Usage Examples

```python
import os
from svc_infra.loaders import NotionLoader

# Load from a database
loader = NotionLoader(
    api_token=os.getenv("NOTION_API_TOKEN"),
    database_ids=["abc123def456..."],
)
contents = await loader.load()

# Load specific pages
loader = NotionLoader(
    api_token=os.getenv("NOTION_API_TOKEN"),
    page_ids=["page1id", "page2id"],
)
contents = await loader.load()

# Index for RAG
from ai_infra import Retriever

retriever = Retriever()
for content in contents:
    retriever.add_text(
        content.content,
        metadata={
            **content.metadata,
            "source_type": "notion"
        }
    )
```

### SlackLoader

Load content from Slack channels and threads:

```python
from svc_infra.loaders import BaseLoader, LoadedContent
import httpx
from typing import Literal
from datetime import datetime, timedelta

class SlackLoader(BaseLoader):
    """Load messages from Slack channels.

    Args:
        bot_token: Slack Bot token (xoxb-...)
        channel_ids: Channel IDs to load from
        days_back: How many days of history to load (default: 30)
        include_threads: Include thread replies
        on_error: Error handling strategy

    Required Bot Scopes:
        - channels:history (public channels)
        - groups:history (private channels)
        - im:history (DMs)
        - mpim:history (group DMs)

    Example:
        >>> loader = SlackLoader(
        ...     bot_token=os.getenv("SLACK_BOT_TOKEN"),
        ...     channel_ids=["C123ABC"],
        ...     days_back=7,
        ... )
        >>> contents = await loader.load()
    """

    BASE_URL = "https://slack.com/api"

    def __init__(
        self,
        bot_token: str,
        channel_ids: list[str],
        *,
        days_back: int = 30,
        include_threads: bool = True,
        on_error: Literal["skip", "raise"] = "skip",
    ):
        super().__init__(on_error=on_error)
        self.bot_token = bot_token
        self.channel_ids = channel_ids
        self.days_back = days_back
        self.include_threads = include_threads

    async def load(self) -> list[LoadedContent]:
        """Load messages from Slack channels."""
        contents = []

        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }

        oldest = (datetime.utcnow() - timedelta(days=self.days_back)).timestamp()

        async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
            for channel_id in self.channel_ids:
                try:
                    channel_content = await self._load_channel(
                        client, channel_id, oldest
                    )
                    contents.extend(channel_content)
                except Exception as e:
                    if self.on_error == "raise":
                        raise

        return contents

    async def _load_channel(
        self,
        client: httpx.AsyncClient,
        channel_id: str,
        oldest: float
    ) -> list[LoadedContent]:
        """Load messages from a channel."""
        contents = []
        cursor = None

        while True:
            params = {
                "channel": channel_id,
                "oldest": str(oldest),
                "limit": 200,
            }
            if cursor:
                params["cursor"] = cursor

            resp = await client.get(
                f"{self.BASE_URL}/conversations.history",
                params=params
            )
            data = resp.json()

            if not data.get("ok"):
                raise RuntimeError(f"Slack API error: {data.get('error')}")

            for message in data.get("messages", []):
                # Skip bot messages and system messages
                if message.get("subtype"):
                    continue

                text = message.get("text", "")
                ts = message.get("ts")
                user = message.get("user", "unknown")

                contents.append(LoadedContent(
                    content=text,
                    source=f"slack://{channel_id}/{ts}",
                    content_type="text/plain",
                    metadata={
                        "loader": "slack",
                        "channel_id": channel_id,
                        "message_ts": ts,
                        "user": user,
                        "timestamp": datetime.fromtimestamp(float(ts)).isoformat(),
                    }
                ))

                # Load thread replies
                if self.include_threads and message.get("reply_count", 0) > 0:
                    thread_contents = await self._load_thread(
                        client, channel_id, ts
                    )
                    contents.extend(thread_contents)

            # Handle pagination
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return contents

    async def _load_thread(
        self,
        client: httpx.AsyncClient,
        channel_id: str,
        thread_ts: str
    ) -> list[LoadedContent]:
        """Load replies in a thread."""
        contents = []

        resp = await client.get(
            f"{self.BASE_URL}/conversations.replies",
            params={"channel": channel_id, "ts": thread_ts}
        )
        data = resp.json()

        if not data.get("ok"):
            return contents

        # Skip first message (parent, already loaded)
        for message in data.get("messages", [])[1:]:
            text = message.get("text", "")
            ts = message.get("ts")
            user = message.get("user", "unknown")

            contents.append(LoadedContent(
                content=text,
                source=f"slack://{channel_id}/{thread_ts}/replies/{ts}",
                content_type="text/plain",
                metadata={
                    "loader": "slack",
                    "channel_id": channel_id,
                    "thread_ts": thread_ts,
                    "message_ts": ts,
                    "user": user,
                    "is_thread_reply": True,
                }
            ))

        return contents
```

### GoogleDocsLoader

Load content from Google Docs:

```python
from svc_infra.loaders import BaseLoader, LoadedContent
from typing import Literal

class GoogleDocsLoader(BaseLoader):
    """Load content from Google Docs.

    Args:
        credentials_file: Path to service account JSON file
        document_ids: List of document IDs to load
        folder_ids: List of folder IDs (loads all docs in folder)
        on_error: Error handling strategy

    Setup:
        1. Create a service account in Google Cloud Console
        2. Enable Google Docs API and Google Drive API
        3. Download credentials JSON
        4. Share documents with service account email

    Example:
        >>> loader = GoogleDocsLoader(
        ...     credentials_file="service-account.json",
        ...     document_ids=["1abc...xyz"],
        ... )
        >>> contents = await loader.load()
    """

    def __init__(
        self,
        credentials_file: str,
        *,
        document_ids: list[str] | None = None,
        folder_ids: list[str] | None = None,
        on_error: Literal["skip", "raise"] = "skip",
    ):
        super().__init__(on_error=on_error)
        self.credentials_file = credentials_file
        self.document_ids = document_ids or []
        self.folder_ids = folder_ids or []

        if not self.document_ids and not self.folder_ids:
            raise ValueError("Must provide document_ids or folder_ids")

    async def load(self) -> list[LoadedContent]:
        """Load content from Google Docs."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                "google-api-python-client required. "
                "Install with: pip install google-api-python-client google-auth"
            )

        # Build credentials and services
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_file,
            scopes=[
                "https://www.googleapis.com/auth/documents.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
        )

        docs_service = build("docs", "v1", credentials=credentials)
        drive_service = build("drive", "v3", credentials=credentials)

        contents = []
        doc_ids = list(self.document_ids)

        # Get document IDs from folders
        for folder_id in self.folder_ids:
            folder_docs = self._list_docs_in_folder(drive_service, folder_id)
            doc_ids.extend(folder_docs)

        # Load each document
        for doc_id in doc_ids:
            try:
                content = self._load_document(docs_service, doc_id)
                contents.append(content)
            except Exception as e:
                if self.on_error == "raise":
                    raise

        return contents

    def _list_docs_in_folder(self, drive_service, folder_id: str) -> list[str]:
        """List Google Docs in a folder."""
        doc_ids = []
        page_token = None

        while True:
            results = drive_service.files().list(
                q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'",
                pageSize=100,
                fields="nextPageToken, files(id)",
                pageToken=page_token
            ).execute()

            doc_ids.extend(f["id"] for f in results.get("files", []))

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return doc_ids

    def _load_document(self, docs_service, doc_id: str) -> LoadedContent:
        """Load a single document."""
        doc = docs_service.documents().get(documentId=doc_id).execute()

        title = doc.get("title", "Untitled")
        text = self._extract_text(doc)

        return LoadedContent(
            content=text,
            source=f"gdocs://{doc_id}",
            content_type="text/plain",
            metadata={
                "loader": "google_docs",
                "document_id": doc_id,
                "title": title,
                "url": f"https://docs.google.com/document/d/{doc_id}",
            }
        )

    def _extract_text(self, doc: dict) -> str:
        """Extract text from document content."""
        lines = []

        for element in doc.get("body", {}).get("content", []):
            if "paragraph" in element:
                para_text = ""
                for elem in element["paragraph"].get("elements", []):
                    if "textRun" in elem:
                        para_text += elem["textRun"].get("content", "")
                lines.append(para_text)

        return "".join(lines)
```

---

## Multi-Source Loading

Combine multiple loaders for unified content loading:

```python
from svc_infra.loaders import GitHubLoader, URLLoader, LoadedContent
from typing import AsyncIterator

class MultiLoader:
    """Load content from multiple sources."""

    def __init__(self, loaders: list):
        self.loaders = loaders

    async def load(self) -> list[LoadedContent]:
        """Load from all sources."""
        all_contents = []

        for loader in self.loaders:
            contents = await loader.load()
            all_contents.extend(contents)

        return all_contents

    async def load_stream(self) -> AsyncIterator[LoadedContent]:
        """Stream content from all sources."""
        for loader in self.loaders:
            contents = await loader.load()
            for content in contents:
                yield content

# Usage
multi_loader = MultiLoader([
    GitHubLoader("nfraxlab/svc-infra", path="docs"),
    ConfluenceLoader(
        base_url="https://company.atlassian.net/wiki",
        space_key="ENG",
        email=os.getenv("CONFLUENCE_EMAIL"),
        api_token=os.getenv("CONFLUENCE_API_TOKEN"),
    ),
    NotionLoader(
        api_token=os.getenv("NOTION_API_TOKEN"),
        database_ids=["abc123..."],
    ),
])

# Load all at once
contents = await multi_loader.load()

# Or stream
async for content in multi_loader.load_stream():
    retriever.add_text(content.content, metadata=content.metadata)
```

---

## Incremental Loading

Load only new or updated content since last sync:

```python
from datetime import datetime
from svc_infra.loaders import BaseLoader, LoadedContent

class IncrementalLoader:
    """Wrapper for incremental/delta loading."""

    def __init__(self, loader: BaseLoader, state_file: str = ".loader_state.json"):
        self.loader = loader
        self.state_file = state_file

    def _load_state(self) -> dict:
        """Load sync state from file."""
        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _save_state(self, state: dict):
        """Save sync state to file."""
        with open(self.state_file, "w") as f:
            json.dump(state, f)

    async def load_incremental(self) -> list[LoadedContent]:
        """Load only new content since last sync."""
        state = self._load_state()
        loader_key = type(self.loader).__name__
        last_sync = state.get(loader_key)

        # Load all content
        contents = await self.loader.load()

        # Filter to new content if we have a last sync time
        if last_sync:
            last_sync_dt = datetime.fromisoformat(last_sync)
            contents = [
                c for c in contents
                if self._is_newer(c, last_sync_dt)
            ]

        # Update state
        state[loader_key] = datetime.utcnow().isoformat()
        self._save_state(state)

        return contents

    def _is_newer(self, content: LoadedContent, since: datetime) -> bool:
        """Check if content is newer than given time."""
        updated = content.metadata.get("updated_at") or content.metadata.get("last_edited_time")
        if updated:
            content_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            return content_dt > since
        return True  # Include if no timestamp

# Usage
incremental = IncrementalLoader(
    NotionLoader(api_token=token, database_ids=["abc"])
)

# First run: loads everything
contents = await incremental.load_incremental()

# Subsequent runs: loads only new/updated content
new_contents = await incremental.load_incremental()
```

---

## Content Chunking

Split loaded content into chunks for embedding:

```python
from svc_infra.loaders import LoadedContent

def chunk_content(
    content: LoadedContent,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[LoadedContent]:
    """Split content into overlapping chunks."""
    text = content.content
    chunks = []

    start = 0
    chunk_num = 0

    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk_text.rfind(". ")
            if last_period > chunk_size // 2:
                end = start + last_period + 1
                chunk_text = text[start:end]

        chunks.append(LoadedContent(
            content=chunk_text,
            source=f"{content.source}#chunk{chunk_num}",
            content_type=content.content_type,
            metadata={
                **content.metadata,
                "chunk_number": chunk_num,
                "chunk_start": start,
                "chunk_end": end,
                "parent_source": content.source,
            }
        ))

        chunk_num += 1
        start = end - overlap

    return chunks

# Usage with ai-infra
from ai_infra import Retriever

retriever = Retriever()
contents = await loader.load()

for content in contents:
    chunks = chunk_content(content, chunk_size=800, overlap=100)
    for chunk in chunks:
        retriever.add_text(chunk.content, metadata=chunk.metadata)
```

---

## Caching Loaded Content

Cache loaded content to avoid repeated API calls:

```python
import hashlib
import json
from pathlib import Path
from svc_infra.loaders import BaseLoader, LoadedContent

class CachedLoader:
    """Wrapper that caches loader results."""

    def __init__(
        self,
        loader: BaseLoader,
        cache_dir: str = ".loader_cache",
        ttl_hours: int = 24,
    ):
        self.loader = loader
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl_hours = ttl_hours

    def _cache_key(self) -> str:
        """Generate cache key from loader configuration."""
        loader_config = {
            "type": type(self.loader).__name__,
            **{k: v for k, v in self.loader.__dict__.items() if not k.startswith("_")}
        }
        config_str = json.dumps(loader_config, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()

    def _cache_file(self) -> Path:
        """Get cache file path."""
        return self.cache_dir / f"{self._cache_key()}.json"

    def _is_cache_valid(self) -> bool:
        """Check if cache exists and is not expired."""
        cache_file = self._cache_file()
        if not cache_file.exists():
            return False

        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        return age_hours < self.ttl_hours

    async def load(self, force_refresh: bool = False) -> list[LoadedContent]:
        """Load from cache or source."""
        cache_file = self._cache_file()

        if not force_refresh and self._is_cache_valid():
            # Load from cache
            with open(cache_file, "r") as f:
                data = json.load(f)
            return [LoadedContent(**item) for item in data]

        # Load from source
        contents = await self.loader.load()

        # Save to cache
        with open(cache_file, "w") as f:
            json.dump([c.dict() for c in contents], f)

        return contents

# Usage
cached = CachedLoader(
    GitHubLoader("nfraxlab/svc-infra", path="docs"),
    cache_dir=".cache/loaders",
    ttl_hours=6,
)

# First call: fetches from GitHub
contents = await cached.load()

# Subsequent calls within 6 hours: returns cached
contents = await cached.load()

# Force refresh
contents = await cached.load(force_refresh=True)
```
