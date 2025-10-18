# Logging Quickstart (svc-infra)

Make your service logs clean, structured, and environment-aware — with optional filtering of noisy access logs (like /metrics).

This README shows:
- how to enable logging with sensible defaults
- how to control level/format via env
- how to hide access logs for paths (e.g., /metrics) only in the environments you choose
- migration from the "old" setup to the new one

---

## 0) Install & import

```python
# main.py (or wherever your app starts)
from svc_infra.app.logging import setup_logging, LogLevelOptions
from svc_infra.app.env import pick
```

---

## 1) Minimal usage (sane defaults)

```python
setup_logging()  # environment-driven defaults
```

What you get by default:
- Level: INFO in prod, DEBUG elsewhere (can be overridden)
- Format: JSON in prod, plain text elsewhere (can be overridden)
- Access-log filtering: drops /metrics only in prod and test (kept in local/dev)

---

## 2) Control level & format

Set via code:

```python
from svc_infra.app.logging.formats import LogFormatOptions
from svc_infra.app.logging import LogLevelOptions

setup_logging(
    level=LogLevelOptions.INFO,          # or "INFO"
    fmt=LogFormatOptions.JSON,           # or "json"
)
```

Or via environment variables:

```bash
# .env or deployment env
LOG_LEVEL=INFO          # DEBUG | INFO | WARNING | ERROR | CRITICAL
LOG_FORMAT=json         # json | plain
```

If you omit both, we default to:
- level = INFO (prod), DEBUG (non-prod)
- format = json (prod), plain (non-prod)

---

## 3) Filter noisy access logs by path

You can drop specific paths from uvicorn/gunicorn access logs (but keep your own app logs).

### 3.1 Environment selection (where filtering is active)

Choose the environments where the filter should be enabled:

```python
# Enable filter in prod+test only (default)
setup_logging(filter_envs=("prod", "test"))

# Disable everywhere
setup_logging(filter_envs=())

# Enable in local+dev (useful if you want silence during local load tests)
setup_logging(filter_envs=("local", "dev", "development"))
```

Accepted names include common synonyms: local, dev, development, test, preview, staging (mapped to test), prod, production.

We detect the current environment from:
- APP_ENV (preferred)
- RAILWAY_ENVIRONMENT_NAME
- default: local

### 3.2 Which paths are dropped

Priority order:
1. drop_paths argument (highest)
2. LOG_DROP_PATHS env
3. default ["/metrics"] (only when the filter is enabled for the current env)

```python
# Code wins over env:
setup_logging(
    filter_envs=("prod", "test"),
    drop_paths=["/metrics", "/health", "/healthz"],
)
```

Or via env:

```bash
# .env
LOG_DROP_PATHS=/metrics,/health,/healthz
```

The filter is tolerant: it matches typical uvicorn/gunicorn access-log formats and drops only those lines for the given paths. Your app's own logs are unaffected.

---

## 4) Full example (typical service)

Old (pre-filter) example:

```python
from svc_infra.app.env import pick
from svc_infra.app.logging import setup_logging, LogLevelOptions

setup_logging(
    level=pick(
        prod=LogLevelOptions.INFO,
        test=LogLevelOptions.INFO,
        dev=LogLevelOptions.DEBUG,
        local=LogLevelOptions.DEBUG,
    )
)
```

New (with access-log filtering and same level policy):

```python
from svc_infra.app.env import pick
from svc_infra.logging.logging import setup_logging, LogLevelOptions

setup_logging(
    level=pick(
        prod=LogLevelOptions.INFO,
        test=LogLevelOptions.INFO,
        dev=LogLevelOptions.DEBUG,
        local=LogLevelOptions.DEBUG,
    ),
    # Keep /metrics noise out of prod/test access logs; keep it visible in local/dev
    filter_envs=("prod", "test"),
    # optionally extend:
    # drop_paths=["/metrics", "/health", "/healthz"],
)
```

---

## 5) Recommended .env keys

```bash
# Which env you're running in (used everywhere in svc-infra)
APP_ENV=local               # local | dev | test | prod (staging/preview map to test)

# Optional log tuning
LOG_LEVEL=DEBUG             # if omitted, defaults by env
LOG_FORMAT=plain            # if omitted, json in prod, plain elsewhere

# Optional: customize which paths are dropped when filter is enabled
LOG_DROP_PATHS=/metrics,/health,/healthz
```

---

## 6) Notes & FAQs

- **Does this hide app errors?**
  No. It only filters web server access logs for matching paths. Your app logs (e.g., logging.getLogger(__name__)) and any error logs still appear.
- **What about frameworks other than uvicorn/gunicorn?**
  The filter targets uvicorn.access and gunicorn.access. If you use another server, you can add a similar filter to its access logger.
- **JSON logs in prod**
  JSON is the default in prod so log aggregators (CloudWatch, Grafana, ELK, etc.) can parse them easily. You can force plain if you prefer.

---

## 7) One-liner quickstart

```python
from svc_infra.app.logging import setup_logging
setup_logging()  # done: sensible defaults + filters in prod/test
```

That's it — structured logs, environment-aware levels/formats, and clean access logs where you want them.
