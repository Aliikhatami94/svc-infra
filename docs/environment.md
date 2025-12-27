# Environment Reference

**svc-infra** uses environment variables for configuration with sensible defaults, environment-aware behavior, and secure secret handling.

---

## Quick Start

```bash
# Minimal production configuration
export APP_ENV=prod
export SQL_URL=postgresql://user:pass@db:5432/mydb
export AUTH_JWT__SECRET=$(openssl rand -hex 32)
export REDIS_URL=redis://redis:6379/0
```

---

## Configuration Philosophy

1. **Explicit over implicit** — Critical settings require explicit configuration
2. **Fail loudly in production** — Missing secrets raise errors, not silent defaults
3. **Environment-aware** — Different defaults for dev/test/prod
4. **Secret file support** — `*_FILE` suffix pattern for Docker/K8s secrets

---

## Environment Detection

### APP_ENV

The primary environment selector:

```bash
export APP_ENV=local    # Local development
export APP_ENV=dev      # Development server
export APP_ENV=test     # Staging/preview
export APP_ENV=prod     # Production
```

**Aliases recognized:**

| Alias | Maps To |
|-------|---------|
| `development` | `dev` |
| `staging`, `preview`, `uat` | `test` |
| `production` | `prod` |

### Environment Detection Order

```python
# Precedence:
# 1. APP_ENV
# 2. RAILWAY_ENVIRONMENT_NAME (Railway.app auto-detection)
# 3. Defaults to "local"
```

### Using pick() for Environment-Specific Values

```python
from svc_infra.app.env import pick

# Choose values by environment
log_level = pick(prod="INFO", nonprod="DEBUG")
debug_mode = pick(prod=False, nonprod=True)
db_pool_size = pick(prod=20, test=5, local=2)

# With explicit overrides
cache_ttl = pick(
    prod=3600,
    test=300,
    dev=60,
    local=10,
)
```

---

## Environment Variables Reference

### App Bootstrap

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `local` | Environment name |
| `ENABLE_LOGGING` | `true` | Enable structured logging |
| `LOG_LEVEL` | Auto | `INFO` in prod, `DEBUG` elsewhere |
| `LOG_FORMAT` | Auto | `json` in prod, `plain` elsewhere |
| `ENABLE_OBS` | `true` | Enable observability (metrics, tracing) |
| `CORS_ALLOW_ORIGINS` | `""` | Comma-separated allowed origins |

### Database (SQL)

| Variable | Default | Description |
|----------|---------|-------------|
| `SQL_URL` | *required* | PostgreSQL connection URL |
| `SQL_URL_FILE` | — | Path to file containing SQL_URL |
| `SQL_POOL_SIZE` | `5` | Connection pool size |
| `SQL_MAX_OVERFLOW` | `10` | Max connections beyond pool |
| `SQL_POOL_TIMEOUT` | `30` | Pool checkout timeout (seconds) |
| `SQL_STATEMENT_TIMEOUT` | `30000` | Query timeout (milliseconds) |

### Database (MongoDB)

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection URL |
| `MONGO_URL_FILE` | — | Path to file containing URL |
| `MONGO_DB` | — | Database name |
| `MONGO_APPNAME` | `svc-infra` | Client app name |
| `MONGO_MIN_POOL` | `0` | Minimum pool size |
| `MONGO_MAX_POOL` | `100` | Maximum pool size |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_JWT__SECRET` | *required in prod* | JWT signing secret |
| `AUTH_JWT__LIFETIME_SECONDS` | `604800` | Token lifetime (7 days) |
| `AUTH_JWT__OLD_SECRETS__0` | — | Previous secret for rotation |
| `AUTH_SESSION_COOKIE_NAME` | `svc_session` | Session cookie key |
| `AUTH_SESSION_COOKIE_SECURE` | `false` | Secure flag for cookies |
| `AUTH_SESSION_COOKIE_SAMESITE` | `lax` | SameSite policy |
| `AUTH_SESSION_COOKIE_MAX_AGE_SECONDS` | `14400` | Session lifetime (4 hours) |

### OAuth Providers

| Variable | Description |
|----------|-------------|
| `AUTH_GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `AUTH_GOOGLE_CLIENT_SECRET` | Google OAuth secret |
| `AUTH_GITHUB_CLIENT_ID` | GitHub OAuth client ID |
| `AUTH_GITHUB_CLIENT_SECRET` | GitHub OAuth secret |
| `AUTH_MS_CLIENT_ID` | Microsoft OAuth client ID |
| `AUTH_MS_CLIENT_SECRET` | Microsoft OAuth secret |
| `AUTH_MS_TENANT` | Microsoft tenant ID |

### MFA/TOTP

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_MFA_ISSUER` | `svc-infra` | TOTP issuer label |
| `AUTH_MFA_DEFAULT_ENABLED_FOR_NEW_USERS` | `false` | Enable MFA on signup |
| `AUTH_MFA_ENFORCE_FOR_ALL_USERS` | `false` | Force MFA globally |
| `AUTH_MFA_RECOVERY_CODES` | `8` | Recovery codes count |
| `AUTH_MFA_PRE_TOKEN_LIFETIME_SECONDS` | `300` | MFA pre-token lifetime |

### Email (SMTP)

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_SMTP_HOST` | — | SMTP hostname |
| `AUTH_SMTP_PORT` | `587` | SMTP port |
| `AUTH_SMTP_USERNAME` | — | SMTP username |
| `AUTH_SMTP_PASSWORD` | — | SMTP password |
| `AUTH_SMTP_FROM` | — | Default from address |
| `AUTH_AUTO_VERIFY_IN_DEV` | `true` | Skip email verification in dev |

### Jobs

| Variable | Default | Description |
|----------|---------|-------------|
| `JOBS_DRIVER` | `memory` | Queue driver (`redis` or `memory`) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL for jobs |
| `JOBS_SCHEDULE_JSON` | — | JSON array of scheduled tasks |

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics |
| `METRICS_PATH` | `/metrics` | Metrics endpoint path |
| `METRICS_DEFAULT_BUCKETS` | `0.005,...,10.0` | Histogram buckets |
| `OBS_SKIP_PATHS` | — | Paths to skip in middleware |
| `SVC_INFRA_DISABLE_PROMETHEUS` | — | Set to `1` to disable |

### Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_URL` | `memory://` | Cache backend URL |
| `CACHE_PREFIX` | `svc:` | Key prefix |
| `CACHE_DEFAULT_TTL` | `3600` | Default TTL (seconds) |

### Tenancy

| Variable | Default | Description |
|----------|---------|-------------|
| `TENANT_HEADER` | `X-Tenant-ID` | Header for tenant ID |
| `TENANT_REQUIRED` | `false` | Require tenant on all requests |

---

## Environment-Specific Examples

### Development (.env)

```bash
# .env (local development)
APP_ENV=local
LOG_LEVEL=DEBUG
LOG_FORMAT=plain

# Database
SQL_URL=postgresql://localhost:5432/myapp_dev

# Auth (dev defaults work)
# No AUTH_JWT__SECRET needed - uses dev fallback

# Jobs (in-memory)
JOBS_DRIVER=memory

# Cache (in-memory)
CACHE_URL=memory://

# CORS for frontend
CORS_ALLOW_ORIGINS=http://localhost:3000
```

### Staging

```bash
# staging.env
APP_ENV=test
LOG_LEVEL=DEBUG
LOG_FORMAT=json

# Database
SQL_URL_FILE=/run/secrets/sql_url

# Auth (required)
AUTH_JWT__SECRET_FILE=/run/secrets/jwt_secret
AUTH_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
AUTH_GOOGLE_CLIENT_SECRET_FILE=/run/secrets/google_secret

# Jobs (Redis)
JOBS_DRIVER=redis
REDIS_URL_FILE=/run/secrets/redis_url

# Email
AUTH_SMTP_HOST=smtp.sendgrid.net
AUTH_SMTP_USERNAME=apikey
AUTH_SMTP_PASSWORD_FILE=/run/secrets/sendgrid_key
AUTH_SMTP_FROM=noreply@staging.example.com
```

### Production

```bash
# production.env
APP_ENV=prod
LOG_LEVEL=INFO
LOG_FORMAT=json

# Database (secrets via files)
SQL_URL_FILE=/run/secrets/sql_url
SQL_POOL_SIZE=20
SQL_MAX_OVERFLOW=30

# Auth (all secrets required)
AUTH_JWT__SECRET_FILE=/run/secrets/jwt_secret
AUTH_JWT__OLD_SECRETS__0_FILE=/run/secrets/jwt_secret_old
AUTH_SESSION_COOKIE_SECURE=true
AUTH_SESSION_COOKIE_SAMESITE=strict

# OAuth
AUTH_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
AUTH_GOOGLE_CLIENT_SECRET_FILE=/run/secrets/google_secret
AUTH_GITHUB_CLIENT_ID=xxx
AUTH_GITHUB_CLIENT_SECRET_FILE=/run/secrets/github_secret

# Jobs (Redis Cluster)
JOBS_DRIVER=redis
REDIS_URL_FILE=/run/secrets/redis_url

# Cache (Redis)
CACHE_URL_FILE=/run/secrets/redis_url

# Email (production SMTP)
AUTH_SMTP_HOST=smtp.sendgrid.net
AUTH_SMTP_PORT=587
AUTH_SMTP_USERNAME=apikey
AUTH_SMTP_PASSWORD_FILE=/run/secrets/sendgrid_key
AUTH_SMTP_FROM=noreply@example.com
AUTH_AUTO_VERIFY_IN_DEV=false

# Observability
METRICS_ENABLED=true

# CORS (specific origins)
CORS_ALLOW_ORIGINS=https://app.example.com,https://admin.example.com
```

---

## Secret Management

### *_FILE Suffix Pattern

For any secret variable, append `_FILE` to read from a file:

```bash
# Instead of:
export AUTH_JWT__SECRET=my-secret-value

# Use file mount:
export AUTH_JWT__SECRET_FILE=/run/secrets/jwt_secret
```

This is the preferred pattern for Docker Swarm and Kubernetes secrets.

### Docker Secrets

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    image: myapp
    environment:
      - SQL_URL_FILE=/run/secrets/sql_url
      - AUTH_JWT__SECRET_FILE=/run/secrets/jwt_secret
    secrets:
      - sql_url
      - jwt_secret

secrets:
  sql_url:
    file: ./secrets/sql_url.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
```

### Kubernetes Secrets

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
stringData:
  sql_url: "postgresql://user:pass@db:5432/mydb"
  jwt_secret: "your-jwt-secret-here"
---
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  template:
    spec:
      containers:
        - name: api
          image: myapp
          env:
            - name: SQL_URL_FILE
              value: /run/secrets/sql_url
            - name: AUTH_JWT__SECRET_FILE
              value: /run/secrets/jwt_secret
          volumeMounts:
            - name: secrets
              mountPath: /run/secrets
              readOnly: true
      volumes:
        - name: secrets
          secret:
            secretName: app-secrets
```

### require_secret() for Safe Loading

```python
from svc_infra.app.env import require_secret, MissingSecretError
import os

# ✅ Safe: Fails in production if not set
secret = require_secret(
    os.getenv("SESSION_SECRET"),
    "SESSION_SECRET",
    dev_default="dev-only-secret-not-for-production",
)

# ❌ NEVER do this: Silent fallback in production
secret = os.getenv("SESSION_SECRET") or "default"  # SECURITY RISK!
```

**Behavior:**
- In `prod`/`staging`: Raises `MissingSecretError` if not set
- In `local`/`dev`: Uses `dev_default` if provided
- Always: Raises if no value and no default

---

## Deployment Platforms

### Railway

Railway auto-sets `RAILWAY_ENVIRONMENT_NAME`:

```bash
# Railway environment mapping
RAILWAY_ENVIRONMENT_NAME=production  → APP_ENV=prod
RAILWAY_ENVIRONMENT_NAME=staging     → APP_ENV=test
```

**Railway variables:**
```bash
# Set in Railway dashboard
SQL_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
AUTH_JWT__SECRET=${{shared.JWT_SECRET}}
```

### Render

```yaml
# render.yaml
services:
  - type: web
    name: api
    env: python
    envVars:
      - key: APP_ENV
        value: prod
      - key: SQL_URL
        fromDatabase:
          name: mydb
          property: connectionString
      - key: AUTH_JWT__SECRET
        generateValue: true
      - key: REDIS_URL
        fromService:
          name: redis
          type: redis
          property: connectionString
```

### AWS ECS/Fargate

```json
{
  "containerDefinitions": [
    {
      "name": "api",
      "image": "myapp",
      "environment": [
        {"name": "APP_ENV", "value": "prod"},
        {"name": "LOG_FORMAT", "value": "json"}
      ],
      "secrets": [
        {
          "name": "SQL_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456:secret:prod/db-url"
        },
        {
          "name": "AUTH_JWT__SECRET",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456:secret:prod/jwt"
        }
      ]
    }
  ]
}
```

### Kubernetes ConfigMap + Secret

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_ENV: "prod"
  LOG_FORMAT: "json"
  METRICS_ENABLED: "true"
  CORS_ALLOW_ORIGINS: "https://app.example.com"
---
# deployment.yaml
spec:
  containers:
    - name: api
      envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
```

---

## Validation

### Startup Validation

svc-infra validates critical settings on startup:

```python
# Automatic validation examples:
# - SQL_URL must be set (raises RuntimeError)
# - AUTH_JWT__SECRET required in prod (raises MissingSecretError)
# - REDIS_URL required if JOBS_DRIVER=redis
```

### Required vs Optional

| Type | Behavior in Production |
|------|------------------------|
| Required | Raises error if missing |
| Required with fallback | Uses fallback, logs warning |
| Optional | Uses default or None |

### Type Coercion

```bash
# Boolean values
ENABLE_LOGGING=true    # true, 1, yes, y → True
ENABLE_LOGGING=false   # false, 0, no, n → False

# Integer values
SQL_POOL_SIZE=20       # Parsed as int

# List values
CORS_ALLOW_ORIGINS=https://a.com,https://b.com  # Comma-separated
```

---

## Override Priorities

Configuration resolution order (highest priority first):

1. **Explicit function parameters**
   ```python
   add_sql_db(app, dsn="postgresql://...")  # Highest priority
   ```

2. **Environment variables**
   ```bash
   export SQL_URL=postgresql://...
   ```

3. **Environment file (.env)**
   ```
   SQL_URL=postgresql://...
   ```

4. **Library defaults**
   ```python
   # Built into svc-infra
   MONGO_MAX_POOL = 100
   ```

---

## Common Errors

### MissingSecretError

```
SECURITY ERROR: AUTH_JWT__SECRET must be set in production/staging environments.
Current environment: prod (raw: 'production')
```

**Solution:** Set the required secret in your environment.

### SQL_URL Not Set

```
RuntimeError: SQL_URL environment variable is required
```

**Solution:** Export `SQL_URL` or use `SQL_URL_FILE`.

### Invalid Environment

```
RuntimeWarning: Unrecognized environment 'staging2', defaulting to 'local'.
```

**Solution:** Use a recognized environment name (local, dev, test, prod).

### File Mount Not Found

```
FileNotFoundError: [Errno 2] No such file: '/run/secrets/jwt_secret'
```

**Solution:** Ensure secrets are mounted correctly in your container.

---

## Troubleshooting

### Environment Not Detected

**Symptom:** App running as `local` when it should be `prod`.

**Diagnosis:**
```python
from svc_infra.app.env import get_current_environment
print(get_current_environment())  # Check actual environment
```

**Solution:**
```bash
export APP_ENV=prod
# Or for Railway:
# Environment is auto-detected from RAILWAY_ENVIRONMENT_NAME
```

### Secrets Not Loading

**Symptom:** `MissingSecretError` despite setting variable.

**Diagnosis:**
```bash
# Check if variable is set
echo $AUTH_JWT__SECRET
# Check file exists (if using _FILE suffix)
cat /run/secrets/jwt_secret
```

**Solution:** Verify the secret is exported in the shell or mounted correctly.

### Wrong Default Values

**Symptom:** Production using development defaults.

**Diagnosis:**
```python
from svc_infra.app.env import IS_PROD
print(f"IS_PROD: {IS_PROD}")  # Should be True
```

**Solution:** Ensure `APP_ENV=prod` is set before app starts.

---

## API Reference

### Environment Functions

```python
from svc_infra.app.env import (
    get_current_environment,  # Returns Environment enum
    get_environment_flags,    # Returns EnvironmentFlags
    pick,                     # Environment-aware value selection
    require_secret,           # Safe secret loading
    MissingSecretError,       # Error for missing secrets
)
```

### Environment Enum

```python
from svc_infra.app.env import Environment

Environment.LOCAL  # "local"
Environment.DEV    # "dev"
Environment.TEST   # "test"
Environment.PROD   # "prod"
```

### EnvironmentFlags

```python
from svc_infra.app.env import get_environment_flags

flags = get_environment_flags()
flags.is_prod   # True if production
flags.is_test   # True if staging/test
flags.is_dev    # True if development
flags.is_local  # True if local
```

---

## See Also

- [Auth Guide](auth.md) — Authentication configuration
- [Database Guide](database.md) — SQL and MongoDB setup
- [Jobs Guide](jobs.md) — Background job configuration
- [Observability](observability.md) — Metrics and logging
- [Security](security.md) — Security best practices
