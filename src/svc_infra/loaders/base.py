"""Base loader class for content loaders.

This module defines the abstract base class that all loaders must implement.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .models import LoadedContent

logger = logging.getLogger(__name__)


# Error handling strategies
ErrorStrategy = Literal["skip", "raise"]


class BaseLoader(ABC):
    """Abstract base class for content loaders.

    All loaders are async-first with sync wrappers provided for convenience.
    Subclasses must implement the `load()` method.

    Attributes:
        on_error: How to handle errors during loading.
            - "skip" (default): Log warning and skip failed items
            - "raise": Raise exception on first failure

    Example:
        >>> class MyLoader(BaseLoader):
        ...     async def load(self) -> list[LoadedContent]:
        ...         # Implement loading logic
        ...         return [LoadedContent(content="...", source="...")]
        >>>
        >>> # Async usage (preferred)
        >>> loader = MyLoader()
        >>> contents = await loader.load()
        >>>
        >>> # Sync usage (convenience)
        >>> contents = loader.load_sync()
    """

    def __init__(
        self,
        on_error: ErrorStrategy = "skip",
    ) -> None:
        """Initialize the base loader.

        Args:
            on_error: Error handling strategy ("skip" or "raise").
        """
        self.on_error = on_error

    @abstractmethod
    async def load(self) -> list[LoadedContent]:
        """Load all content from the source.

        This is the main method that subclasses must implement.

        Returns:
            List of LoadedContent objects.

        Raises:
            Various exceptions depending on the loader and error strategy.
        """
        ...

    async def aiter(self) -> AsyncIterator[LoadedContent]:
        """Iterate over loaded content asynchronously.

        This is useful for progress tracking or streaming large datasets.
        Default implementation loads all content first, but subclasses
        can override for true streaming.

        Yields:
            LoadedContent objects as they are loaded.

        Example:
            >>> async for content in loader.aiter():
            ...     print(f"Loaded: {content.source}")
            ...     process(content)
        """
        for content in await self.load():
            yield content

    def load_sync(self) -> list[LoadedContent]:
        """Synchronous wrapper for load().

        Creates a new event loop if needed. Prefer the async version
        when running in an async context.

        Returns:
            List of LoadedContent objects.

        Example:
            >>> # In a script or notebook
            >>> loader = GitHubLoader("nfraxlab/svc-infra", path="docs")
            >>> contents = loader.load_sync()
        """
        try:
            # Check if we're already in an async context
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(self.load())

        # Already in async context - use nest_asyncio if available
        try:
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(self.load())
        except ImportError:
            raise RuntimeError(
                "Cannot call load_sync() from within an async context. "
                "Use 'await loader.load()' instead, or install nest_asyncio: "
                "pip install nest-asyncio"
            )

    def _handle_error(self, error: Exception, context: str) -> None:
        """Handle an error according to the error strategy.

        Args:
            error: The exception that occurred.
            context: Description of what was being done (for logging).

        Raises:
            The original exception if on_error="raise".
        """
        if self.on_error == "raise":
            raise error
        else:
            logger.warning(f"Skipping {context}: {error}")

    def __repr__(self) -> str:
        """Return string representation of the loader."""
        return f"{self.__class__.__name__}(on_error={self.on_error!r})"
