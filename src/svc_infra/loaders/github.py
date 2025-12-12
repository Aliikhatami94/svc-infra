"""GitHub content loader.

Load files from GitHub repositories using the GitHub API.
"""

from __future__ import annotations

import fnmatch
import logging
import os
from typing import Any

import httpx

from .base import BaseLoader, ErrorStrategy
from .models import LoadedContent

logger = logging.getLogger(__name__)


class GitHubLoader(BaseLoader):
    """Load files from a GitHub repository.

    Fetches files matching a pattern from a GitHub repo using the GitHub API.
    Supports public repos and private repos (with token).

    Args:
        repo: Repository in "owner/repo" format (e.g., "nfraxlab/svc-infra")
        path: Path within repo to load from (e.g., "docs", "examples/src").
            Empty string means repo root.
        branch: Branch name (default: "main")
        pattern: Glob pattern for files to include (default: "*.md").
            Use "*" to match all files.
        token: GitHub token for private repos or higher rate limits.
            Falls back to GITHUB_TOKEN environment variable.
        recursive: Whether to search subdirectories (default: True)
        skip_patterns: List of patterns to skip. Default patterns are:
            __pycache__, *.pyc, *.pyo, .git, node_modules, *.lock, .env*
        extra_metadata: Additional metadata to attach to all loaded content.
        on_error: How to handle errors ("skip" or "raise"). Default: "skip"

    Example:
        >>> # Load all markdown from docs/
        >>> loader = GitHubLoader("nfraxlab/svc-infra", path="docs")
        >>> contents = await loader.load()
        >>> for c in contents:
        ...     print(f"Loaded: {c.source}")
        >>>
        >>> # Load Python files from examples
        >>> loader = GitHubLoader(
        ...     "nfraxlab/svc-infra",
        ...     path="examples/src",
        ...     pattern="*.py",
        ...     skip_patterns=["__pycache__", "test_*"],
        ... )
        >>> contents = await loader.load()
        >>>
        >>> # Private repo with token
        >>> loader = GitHubLoader(
        ...     "myorg/private-repo",
        ...     token="ghp_xxxx",  # or set GITHUB_TOKEN env var
        ... )
        >>> contents = await loader.load()

    Note:
        - GitHub API rate limits: 60 requests/hour unauthenticated,
          5000 requests/hour with token
        - Large repos may require multiple API calls (tree is fetched recursively)
        - Binary files are automatically skipped
    """

    GITHUB_API = "https://api.github.com"
    GITHUB_RAW = "https://raw.githubusercontent.com"

    DEFAULT_SKIP_PATTERNS: list[str] = [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".git",
        ".github",
        "node_modules",
        "*.lock",
        ".env*",
        ".DS_Store",
        "*.egg-info",
        "dist",
        "build",
        "*.min.js",
        "*.min.css",
    ]

    # Content types by extension
    CONTENT_TYPES: dict[str, str] = {
        "md": "text/markdown",
        "py": "text/x-python",
        "json": "application/json",
        "yaml": "text/yaml",
        "yml": "text/yaml",
        "toml": "text/toml",
        "sql": "text/x-sql",
        "html": "text/html",
        "css": "text/css",
        "js": "text/javascript",
        "ts": "text/typescript",
        "tsx": "text/typescript",
        "jsx": "text/javascript",
        "txt": "text/plain",
        "rst": "text/x-rst",
        "ini": "text/plain",
        "cfg": "text/plain",
        "sh": "text/x-shellscript",
        "bash": "text/x-shellscript",
        "zsh": "text/x-shellscript",
    }

    def __init__(
        self,
        repo: str,
        path: str = "",
        branch: str = "main",
        pattern: str = "*.md",
        token: str | None = None,
        recursive: bool = True,
        skip_patterns: list[str] | None = None,
        extra_metadata: dict[str, Any] | None = None,
        on_error: ErrorStrategy = "skip",
    ) -> None:
        """Initialize the GitHub loader.

        Args:
            repo: Repository in "owner/repo" format
            path: Path within repo (empty string for root)
            branch: Branch name
            pattern: Glob pattern for files to include
            token: GitHub token (or use GITHUB_TOKEN env var)
            recursive: Search subdirectories
            skip_patterns: Patterns to skip (overrides defaults if provided)
            extra_metadata: Additional metadata for all content
            on_error: Error handling strategy
        """
        super().__init__(on_error=on_error)

        # Validate repo format
        if "/" not in repo or repo.count("/") != 1:
            raise ValueError(f"Invalid repo format: {repo!r}. Expected 'owner/repo' format.")

        self.repo = repo
        self.path = path.strip("/")
        self.branch = branch
        self.pattern = pattern
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.recursive = recursive
        self.skip_patterns = (
            skip_patterns if skip_patterns is not None else self.DEFAULT_SKIP_PATTERNS
        )
        self.extra_metadata = extra_metadata or {}

    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "svc-infra-loader",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _should_skip(self, file_path: str) -> bool:
        """Check if file should be skipped based on patterns."""
        # Check each component of the path against skip patterns
        parts = file_path.split("/")
        for part in parts:
            for skip in self.skip_patterns:
                if fnmatch.fnmatch(part, skip):
                    return True
        return False

    def _matches_pattern(self, filename: str) -> bool:
        """Check if filename matches the include pattern."""
        # Support multiple patterns separated by |
        patterns = self.pattern.split("|")
        return any(fnmatch.fnmatch(filename, p.strip()) for p in patterns)

    def _guess_content_type(self, path: str) -> str:
        """Guess content type from file extension."""
        if "." not in path:
            return "text/plain"
        ext = path.rsplit(".", 1)[-1].lower()
        return self.CONTENT_TYPES.get(ext, "text/plain")

    async def load(self) -> list[LoadedContent]:
        """Load all matching files from the GitHub repository.

        Returns:
            List of LoadedContent objects for each matching file.

        Raises:
            ValueError: If repository not found or access denied.
            httpx.HTTPError: If API request fails and on_error="raise".
        """
        contents: list[LoadedContent] = []
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch repository tree
            tree_url = f"{self.GITHUB_API}/repos/{self.repo}/git/trees/{self.branch}"
            if self.recursive:
                tree_url += "?recursive=1"

            logger.debug(f"Fetching tree from: {tree_url}")

            try:
                resp = await client.get(tree_url, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise ValueError(
                        f"Repository or branch not found: {self.repo}@{self.branch}"
                    ) from e
                elif e.response.status_code == 403:
                    # Check if it's rate limiting
                    remaining = e.response.headers.get("X-RateLimit-Remaining", "?")
                    raise ValueError(
                        f"GitHub API access denied (rate limit remaining: {remaining}). "
                        f"Set GITHUB_TOKEN environment variable for higher limits."
                    ) from e
                raise

            tree_data = resp.json()
            tree = tree_data.get("tree", [])
            truncated = tree_data.get("truncated", False)

            if truncated:
                logger.warning(
                    "Repository tree was truncated by GitHub API. "
                    "Some files may not be loaded. Consider narrowing the path."
                )

            # Filter files by path, pattern, and skip patterns
            path_prefix = f"{self.path}/" if self.path else ""
            matching_files: list[str] = []

            for item in tree:
                # Only process files (blobs)
                if item.get("type") != "blob":
                    continue

                file_path = item.get("path", "")

                # Must be under specified path
                if path_prefix and not file_path.startswith(path_prefix):
                    continue

                # Check skip patterns
                if self._should_skip(file_path):
                    logger.debug(f"Skipping (matches skip pattern): {file_path}")
                    continue

                # Check include pattern against filename
                filename = file_path.split("/")[-1]
                if not self._matches_pattern(filename):
                    continue

                matching_files.append(file_path)

            logger.info(f"Found {len(matching_files)} matching files in {self.repo}")

            # Fetch content for each matching file
            for file_path in matching_files:
                raw_url = f"{self.GITHUB_RAW}/{self.repo}/{self.branch}/{file_path}"

                try:
                    resp = await client.get(raw_url, headers=headers)
                    resp.raise_for_status()
                    content = resp.text
                except httpx.HTTPError as e:
                    msg = f"Failed to fetch {file_path}: {e}"
                    if self.on_error == "raise":
                        raise RuntimeError(msg) from e
                    logger.warning(msg)
                    continue

                # Build relative path from specified base path
                rel_path = file_path[len(path_prefix) :] if path_prefix else file_path

                loaded = LoadedContent(
                    content=content,
                    source=f"github://{self.repo}/{file_path}",
                    content_type=self._guess_content_type(file_path),
                    metadata={
                        "loader": "github",
                        "repo": self.repo,
                        "branch": self.branch,
                        "path": rel_path,
                        "full_path": file_path,
                        **self.extra_metadata,
                    },
                )
                contents.append(loaded)
                logger.debug(f"Loaded: {file_path} ({len(content)} chars)")

        return contents

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"GitHubLoader({self.repo!r}, path={self.path!r}, "
            f"branch={self.branch!r}, pattern={self.pattern!r})"
        )
