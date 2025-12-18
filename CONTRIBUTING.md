# Contributing to svc-infra

Thank you for your interest in contributing to svc-infra! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to build great software.

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry for dependency management
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/nfraxlab/svc-infra.git
cd svc-infra

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell

# Run tests
pytest -q

# Run linting
ruff check

# Run type checking
mypy src
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

- Follow the existing code style
- Add type hints to all functions
- Write docstrings for public APIs
- Add tests for new functionality

### 3. Run Quality Checks

```bash
# Format code
ruff format

# Check for issues
ruff check

# Run type checker
mypy src

# Run tests
pytest -q
```

### 4. Submit a Pull Request

- Write a clear description of your changes
- Reference any related issues
- Ensure all checks pass

## Code Standards

### Type Hints

All functions must have complete type hints:

```python
# ✅ Good
def process_request(data: dict[str, Any], timeout: float = 30.0) -> Response:
    ...

# ❌ Bad
def process_request(data, timeout=30.0):
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def calculate_hash(data: bytes, algorithm: str = "sha256") -> str:
    """Calculate the hash of the given data.

    Args:
        data: The bytes to hash.
        algorithm: The hash algorithm to use.

    Returns:
        The hexadecimal hash string.

    Raises:
        ValueError: If the algorithm is not supported.
    """
```

### Error Handling

- Use specific exception types, not bare `Exception`
- Always log errors before re-raising
- Never silently swallow exceptions

```python
# ✅ Good
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise

# ❌ Bad
try:
    result = risky_operation()
except Exception:
    pass
```

### Testing

- Write tests for all new functionality
- Test both success and error paths
- Use pytest fixtures for common setup

```python
def test_cache_returns_stored_value():
    cache = MemoryCache()
    cache.set("key", "value", ttl=60)
    assert cache.get("key") == "value"

def test_cache_raises_on_expired():
    cache = MemoryCache()
    cache.set("key", "value", ttl=-1)  # Already expired
    with pytest.raises(KeyError):
        cache.get("key")
```

## Project Structure

```
svc-infra/
├── src/svc_infra/     # Main package
│   ├── api/           # FastAPI framework
│   ├── auth/          # Authentication & authorization
│   ├── cache/         # Caching backends
│   ├── db/            # Database utilities
│   ├── jobs/          # Background job processing
│   ├── obs/           # Observability (logging, metrics)
│   ├── storage/       # File storage backends
│   └── webhooks/      # Webhook management
├── tests/             # Test files
├── docs/              # Documentation
└── examples/          # Example applications
```

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format. This enables automated CHANGELOG generation.

**Format:** `type(scope): description`

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `refactor:` Code change that neither fixes a bug nor adds a feature
- `perf:` Performance improvement
- `test:` Adding or updating tests
- `ci:` CI/CD changes
- `chore:` Maintenance tasks

**Examples:**
```
feat: add Redis cache backend
fix: handle connection timeout in database pool
docs: update authentication guide
refactor: extract retry logic to shared utility
test: add unit tests for webhook signing
```

**Bad examples (will be grouped as "Other Changes"):**
```
Refactor code for improved readability  ← Missing type prefix!
updating docs                           ← Missing type prefix!
bug fix                                 ← Missing type prefix!
```

## Deprecation Guidelines

When removing or changing public APIs, follow our [Deprecation Policy](DEPRECATION.md).

### When to Deprecate vs Remove

- **Deprecate first** if the feature has any external users
- **Immediate removal** only for security vulnerabilities (see DEPRECATION.md)
- **Never remove** without at least 2 minor versions of deprecation warnings

### How to Add Deprecation Warnings

Use the `@deprecated` decorator:

```python
from svc_infra.utils.deprecation import deprecated

@deprecated(
    version="1.2.0",
    reason="Use new_function() instead",
    removal_version="1.4.0"
)
def old_function():
    ...
```

For deprecated parameters:

```python
from svc_infra.utils.deprecation import deprecated_parameter

def my_function(new_param: str, old_param: str | None = None):
    if old_param is not None:
        deprecated_parameter(
            name="old_param",
            version="1.2.0",
            reason="Use new_param instead"
        )
        new_param = old_param
    ...
```

### Documentation Requirements

When deprecating a feature, you must:

1. Add `@deprecated` decorator or call `deprecated_parameter()`
2. Update the docstring with deprecation notice
3. Add entry to "Deprecated Features Registry" in DEPRECATION.md
4. Add entry to CHANGELOG.md under "Deprecated" section

### Migration Guide Requirements

For significant deprecations, create a migration guide:

1. Create `docs/migrations/v{version}.md`
2. Explain what changed and why
3. Provide before/after code examples
4. Link from the deprecation warning message

## Required Checks Before PR

- [ ] No hardcoded secrets or default fallbacks
- [ ] No silent exception swallowing
- [ ] Parameterized SQL queries (no string interpolation)
- [ ] `ruff check` passes
- [ ] `mypy src` passes
- [ ] `pytest` passes
- [ ] Deprecations follow the deprecation policy

## Questions?

- Open an issue for bugs or feature requests
- Join our discussions for general questions

Thank you for contributing!
