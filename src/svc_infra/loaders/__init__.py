"""
Content loaders for fetching from remote and local sources.

This module provides async-first loaders for GitHub, URLs, and other sources.
All loaders return a consistent `LoadedContent` format that is compatible
with ai-infra's Retriever.add_text() method.

Quick Start:
    >>> from svc_infra.loaders import GitHubLoader, URLLoader
    >>>
    >>> # Load from GitHub
    >>> loader = GitHubLoader("nfraxlab/svc-infra", path="docs")
    >>> contents = await loader.load()
    >>>
    >>> # Load from URL
    >>> loader = URLLoader("https://example.com/guide.md")
    >>> contents = await loader.load()
    >>>
    >>> # Sync usage (for scripts/notebooks)
    >>> contents = loader.load_sync()

With ai-infra Retriever:
    >>> from ai_infra import Retriever
    >>> from svc_infra.loaders import GitHubLoader
    >>>
    >>> retriever = Retriever()
    >>> loader = GitHubLoader("nfraxlab/svc-infra", path="docs")
    >>>
    >>> for content in await loader.load():
    ...     retriever.add_text(content.content, metadata=content.metadata)

Convenience Functions:
    >>> from svc_infra.loaders import load_github, load_url
    >>>
    >>> # One-liner loading
    >>> contents = await load_github("nfraxlab/svc-infra", path="docs")
    >>> contents = await load_url("https://example.com/guide.md")

Available Loaders:
    - GitHubLoader: Load files from GitHub repositories
    - URLLoader: Load content from URLs (with HTML text extraction)

Future Loaders (planned):
    - S3Loader: Load files from S3-compatible storage
    - NotionLoader: Load pages from Notion
    - ConfluenceLoader: Load pages from Confluence
"""

from .base import BaseLoader
from .github import GitHubLoader
from .models import LoadedContent, LoadedDocument, to_loaded_documents
from .url import URLLoader


async def load_github(
    repo: str,
    path: str = "",
    branch: str = "main",
    pattern: str = "*.md",
    **kwargs,
) -> list[LoadedContent]:
    """Convenience function to load content from GitHub.

    This is a shortcut for creating a GitHubLoader and calling load().

    Args:
        repo: Repository in "owner/repo" format
        path: Path within repo (empty for root)
        branch: Branch name (default: "main")
        pattern: Glob pattern for files (default: "*.md")
        **kwargs: Additional arguments passed to GitHubLoader

    Returns:
        List of LoadedContent objects.

    Example:
        >>> contents = await load_github("nfraxlab/svc-infra", path="docs")
        >>> for c in contents:
        ...     print(f"{c.source}: {len(c.content)} chars")
    """
    loader = GitHubLoader(repo, path=path, branch=branch, pattern=pattern, **kwargs)
    return await loader.load()


async def load_url(
    urls: str | list[str],
    **kwargs,
) -> list[LoadedContent]:
    """Convenience function to load content from URL(s).

    This is a shortcut for creating a URLLoader and calling load().

    Args:
        urls: Single URL or list of URLs to load
        **kwargs: Additional arguments passed to URLLoader

    Returns:
        List of LoadedContent objects.

    Example:
        >>> # Single URL
        >>> contents = await load_url("https://example.com/guide.md")
        >>>
        >>> # Multiple URLs
        >>> contents = await load_url([
        ...     "https://example.com/page1",
        ...     "https://example.com/page2",
        ... ])
    """
    loader = URLLoader(urls, **kwargs)
    return await loader.load()


def load_github_sync(
    repo: str,
    path: str = "",
    branch: str = "main",
    pattern: str = "*.md",
    **kwargs,
) -> list[LoadedContent]:
    """Synchronous convenience function to load content from GitHub.

    This is a shortcut for creating a GitHubLoader and calling load_sync().
    Use this in scripts, notebooks, or non-async contexts.

    Args:
        repo: Repository in "owner/repo" format
        path: Path within repo (empty for root)
        branch: Branch name (default: "main")
        pattern: Glob pattern for files (default: "*.md")
        **kwargs: Additional arguments passed to GitHubLoader

    Returns:
        List of LoadedContent objects.

    Example:
        >>> # In a script or notebook (no await needed)
        >>> contents = load_github_sync("nfraxlab/svc-infra", path="docs")
        >>> for c in contents:
        ...     print(f"{c.source}: {len(c.content)} chars")
    """
    loader = GitHubLoader(repo, path=path, branch=branch, pattern=pattern, **kwargs)
    return loader.load_sync()


def load_url_sync(
    urls: str | list[str],
    **kwargs,
) -> list[LoadedContent]:
    """Synchronous convenience function to load content from URL(s).

    This is a shortcut for creating a URLLoader and calling load_sync().
    Use this in scripts, notebooks, or non-async contexts.

    Args:
        urls: Single URL or list of URLs to load
        **kwargs: Additional arguments passed to URLLoader

    Returns:
        List of LoadedContent objects.

    Example:
        >>> # In a script or notebook (no await needed)
        >>> contents = load_url_sync("https://example.com/guide.md")
    """
    loader = URLLoader(urls, **kwargs)
    return loader.load_sync()


__all__ = [
    # Base classes
    "BaseLoader",
    "LoadedContent",
    # Compatibility
    "LoadedDocument",
    "to_loaded_documents",
    # Loaders
    "GitHubLoader",
    "URLLoader",
    # Async convenience functions
    "load_github",
    "load_url",
    # Sync convenience functions
    "load_github_sync",
    "load_url_sync",
]
