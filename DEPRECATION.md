# Deprecation Policy

This document outlines how deprecated features are handled in `svc-infra`.

## Deprecation Timeline

Features are deprecated for a **minimum of 2 minor versions** before removal:

| Version | Action |
|---------|--------|
| v1.2.0 | Feature marked deprecated with warning |
| v1.3.0 | Deprecation warning continues |
| v1.4.0 | Feature may be removed |

**Example**: A feature deprecated in v1.2.0 will emit warnings through v1.3.x and may be removed in v1.4.0.

## How Deprecations Are Announced

1. **CHANGELOG.md**: All deprecations are listed in the "Deprecated" section of the release notes
2. **Runtime Warnings**: Deprecated features emit `DeprecationWarning` when used
3. **Documentation**: Deprecated features are marked with `.. deprecated::` directive
4. **IDE Support**: Type hints and docstrings include deprecation notices

## Identifying Deprecated Features

### Runtime Warnings

Deprecated features emit `DeprecationWarning`:

```python
import warnings
warnings.filterwarnings("default", category=DeprecationWarning, module="svc_infra")

# Now you'll see deprecation warnings when using deprecated features
from svc_infra.auth import OldAuthClass  # Warns: OldAuthClass is deprecated, use NewAuthClass
```

### In Tests

Enable deprecation warnings in pytest:

```ini
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
filterwarnings = [
    "error::DeprecationWarning:svc_infra.*",
]
```

### Using the Decorator

We provide a `@deprecated` decorator for marking deprecated functions and classes:

```python
from svc_infra.utils.deprecation import deprecated

@deprecated(
    version="1.2.0",
    reason="Use new_function() instead",
    removal_version="1.4.0"
)
def old_function():
    pass
```

## Migration Guide Requirements

When deprecating a feature, maintainers must provide:

1. **Clear reason** for deprecation
2. **Recommended replacement** (if applicable)
3. **Migration path** with code examples
4. **Timeline** for removal

Example deprecation notice:

```
DeprecationWarning: `easy_service_app()` is deprecated since v1.2.0 and will be
removed in v1.4.0. Use `create_app()` instead. See migration guide at:
https://docs.nfrax.com/svc-infra/migrations/1.2.0
```

## Exception Policy for Security Issues

Security vulnerabilities are exempt from the standard deprecation timeline:

| Severity | Action |
|----------|--------|
| **Critical** | Immediate removal in patch release (e.g., v1.2.1) |
| **High** | Removal in next minor release with CVE notice |
| **Medium** | Standard deprecation with accelerated timeline (1 minor version) |
| **Low** | Standard deprecation timeline (2 minor versions) |

Security-related removals will be:
- Announced via GitHub Security Advisory
- Listed in CHANGELOG with `[SECURITY]` prefix
- Communicated to users via release notes

## Deprecated Features Registry

| Feature | Deprecated In | Removal In | Replacement |
|---------|---------------|------------|-------------|
| *None currently* | — | — | — |

## Questions?

If you have questions about deprecations or need help migrating, please:
- Open a [GitHub Discussion](https://github.com/nfraxlab/svc-infra/discussions)
- Submit feedback at https://www.nfrax.com/?feedback=1
