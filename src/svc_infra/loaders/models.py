"""Data models for content loaders.

This module defines the core data structures used by all loaders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoadedContent:
    """Content loaded from a remote or local source.

    This is the standard output format for all loaders. It's designed to be
    compatible with ai-infra's Retriever.add_text() method.

    Attributes:
        content: The text content that was loaded.
        metadata: Flexible metadata dict. Loaders add source-specific metadata
            (e.g., repo, path, branch for GitHub). Users can add custom metadata
            via the loader's `extra_metadata` parameter.
        source: Source identifier (URL, file path, GitHub URI, etc.).
            Format varies by loader:
            - GitHubLoader: "github://owner/repo/path"
            - URLLoader: "https://example.com/page"
            - S3Loader: "s3://bucket/key"
        content_type: MIME type or content category (e.g., "text/markdown",
            "text/x-python", "text/html"). None if unknown.
        encoding: Character encoding (default: utf-8).

    Example:
        >>> content = LoadedContent(
        ...     content="# Authentication\\n\\nThis guide covers...",
        ...     source="github://nfraxlab/svc-infra/docs/auth.md",
        ...     content_type="text/markdown",
        ...     metadata={"repo": "nfraxlab/svc-infra", "path": "docs/auth.md"},
        ... )
        >>>
        >>> # Use with ai-infra Retriever
        >>> retriever.add_text(content.content, metadata=content.metadata)
    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    content_type: str | None = None
    encoding: str = "utf-8"

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        # Ensure metadata is a dict
        if self.metadata is None:
            self.metadata = {}

        # Add source to metadata if not already present
        if self.source and "source" not in self.metadata:
            self.metadata["source"] = self.source

    def to_tuple(self) -> tuple[str, dict[str, Any]]:
        """Convert to (content, metadata) tuple.

        This format is compatible with ai-infra's Retriever.add_text() and
        the legacy LoadedDocument type from ai-infra/retriever/loaders.py.

        Returns:
            Tuple of (content, metadata).

        Example:
            >>> content, metadata = loaded_content.to_tuple()
            >>> retriever.add_text(content, metadata=metadata)
        """
        return (self.content, self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with all fields, suitable for JSON serialization.

        Example:
            >>> data = loaded_content.to_dict()
            >>> json.dumps(data)
        """
        return {
            "content": self.content,
            "metadata": self.metadata,
            "source": self.source,
            "content_type": self.content_type,
            "encoding": self.encoding,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoadedContent:
        """Create LoadedContent from a dictionary.

        Args:
            data: Dictionary with content, metadata, source, etc.

        Returns:
            New LoadedContent instance.

        Example:
            >>> data = {"content": "Hello", "source": "test.txt"}
            >>> content = LoadedContent.from_dict(data)
        """
        return cls(
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            source=data.get("source", ""),
            content_type=data.get("content_type"),
            encoding=data.get("encoding", "utf-8"),
        )

    def __len__(self) -> int:
        """Return the length of the content."""
        return len(self.content)

    def __bool__(self) -> bool:
        """Return True if content is non-empty."""
        return bool(self.content.strip())


# Type alias for backward compatibility with ai-infra loaders
LoadedDocument = tuple[str, dict[str, Any]]


def to_loaded_documents(contents: list[LoadedContent]) -> list[LoadedDocument]:
    """Convert LoadedContent list to LoadedDocument list.

    This is a compatibility helper for code that expects the legacy
    (content, metadata) tuple format from ai-infra/retriever/loaders.py.

    Args:
        contents: List of LoadedContent objects.

    Returns:
        List of (content, metadata) tuples.

    Example:
        >>> contents = await loader.load()
        >>> documents = to_loaded_documents(contents)
        >>> for content, metadata in documents:
        ...     retriever.add_text(content, metadata=metadata)
    """
    return [c.to_tuple() for c in contents]
