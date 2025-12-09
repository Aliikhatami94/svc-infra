# ADR-0001: Content Loaders Architecture

**Status**: Accepted  
**Date**: 2024-12-09  
**Decision Makers**: @alikhatami

## Context

nfrax-api and other projects need to load content from remote sources (GitHub, URLs, S3, etc.) for RAG applications. Currently:

1. **nfrax-api** has 80+ lines of custom GitHub fetching code in `docs_retriever.py`
2. **ai-infra** has file loaders in `retriever/loaders.py` but only for local files
3. Each project duplicates remote fetching logic

We need reusable loaders that:
- Work standalone (not tied to any specific embedding/RAG system)
- Integrate seamlessly with ai-infra Retriever
- Are async-first (modern Python, better performance)
- Have consistent interfaces and output formats

## Decision

Create a `svc_infra.loaders` module that provides:

### 1. Async-First Design

All loaders are async with sync wrappers for convenience:

```python
# Async (preferred)
contents = await loader.load()

# Sync wrapper (for scripts, notebooks)
contents = loader.load_sync()
```

**Rationale**: Modern applications are async. Sync wrappers use `asyncio.run()` for backward compatibility.

### 2. Unified Output Format

All loaders return `list[LoadedContent]`:

```python
@dataclass
class LoadedContent:
    content: str                    # The text content
    metadata: dict[str, Any]        # Flexible metadata
    source: str                     # Source identifier (URL, path, etc.)
    content_type: str | None        # MIME type or category
```

**Rationale**:
- Consistent format across all loaders
- Compatible with ai-infra Retriever's `add_text(content, metadata=metadata)` pattern
- `metadata` dict is flexible enough for any loader's specific needs

### 3. Loader Interface

```python
class BaseLoader(ABC):
    @abstractmethod
    async def load(self) -> list[LoadedContent]:
        """Load all content from the source."""
        ...

    def load_sync(self) -> list[LoadedContent]:
        """Synchronous wrapper."""
        return asyncio.run(self.load())
```

**Rationale**: Simple interface. Each loader handles its own configuration in `__init__`.

### 4. Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│                       Application                            │
│  from svc_infra.loaders import GitHubLoader                 │
│  contents = await GitHubLoader(...).load()                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    svc-infra.loaders                         │
│  GitHubLoader, URLLoader, S3Loader (future)                 │
│  - Handles fetching, filtering, text extraction             │
│  - Returns LoadedContent with standardized metadata         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ai-infra (optional)                        │
│  retriever.add_from_loader(loader)                          │
│  - Thin wrappers that use svc-infra loaders                 │
│  - Handles embedding and storage                            │
└─────────────────────────────────────────────────────────────┘
```

**Rationale**:
- Loaders are infrastructure (svc-infra)
- Embedding/RAG is AI (ai-infra)
- Clear separation, reusable components

### 5. Error Handling Strategy

- **Skip on error** (default): Failed files are logged and skipped
- **Fail on error** (optional): Raise exception on first failure

```python
loader = GitHubLoader(repo, on_error="skip")  # default
loader = GitHubLoader(repo, on_error="raise")  # strict mode
```

**Rationale**: Most use cases prefer loading what's available over failing completely.

### 6. Rate Limiting and Retries

Built-in for external APIs:

```python
loader = GitHubLoader(
    repo,
    max_retries=3,
    retry_delay=1.0,
    rate_limit_delay=0.1,  # Delay between requests
)
```

**Rationale**: GitHub API has rate limits. Good defaults prevent hitting them.

## Implementation Plan

### Phase 1: Core (Priority)
- `LoadedContent` model
- `BaseLoader` abstract class
- `GitHubLoader` - Most common use case
- `URLLoader` - Simple web content loading

### Phase 2: Cloud Storage (Future)
- `S3Loader` - AWS S3, DigitalOcean Spaces, Minio
- `GCSLoader` - Google Cloud Storage

### Phase 3: SaaS (Future)
- `NotionLoader` - Notion pages
- `ConfluenceLoader` - Confluence pages
- `SlackLoader` - Slack messages

## Consequences

### Positive
- Single implementation for all projects
- Consistent interface and output format
- Easy integration with ai-infra Retriever
- Async-first with sync compatibility
- Well-tested, reusable components

### Negative
- New dependency for projects using loaders
- svc-infra becomes a dependency for ai-infra's remote loading

### Neutral
- Loaders are opt-in (don't affect existing svc-infra users)

## Alternatives Considered

### 1. Implement loaders in ai-infra

**Rejected**: Loaders are infrastructure, not AI. Other projects may want loaders without RAG.

### 2. Use LangChain document loaders

**Rejected**:
- Heavy dependency for simple loading
- Different interfaces/abstractions
- We need async-first, LangChain loaders are sync-first

### 3. Keep loaders in each project

**Rejected**: Code duplication, inconsistent implementations, maintenance burden.

## References

- Phase 24 in svc-infra PLAN.md
- Phase 6.9 in ai-infra PLAN.md
- nfrax-api/src/nfrax_api/mcp/docs_retriever.py (current implementation)
