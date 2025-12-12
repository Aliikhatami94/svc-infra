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
