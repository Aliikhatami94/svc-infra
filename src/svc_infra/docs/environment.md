# Environment Reference

This guide consolidates every environment variable consumed by the svc-infra helpers in FastAPI, jobs, observability, security, and webhooks. Defaults shown below reflect the library's fallbacks when a variable is absent. Where a helper relies on `svc_infra.app.pick`, the note column calls out the environment-specific behavior.

## FastAPI helpers

### App bootstrap (`easy_service_app` / `setup_service_api`)

| Variable | Default | Consumed by | Notes |
| --- | --- | --- | --- |
| `ENABLE_LOGGING` | `true` | `EasyAppOptions.from_env()` | Disables `setup_logging` when set to false. |
| `LOG_LEVEL` | Auto (`INFO` in prod/test, `DEBUG` in dev/local via `pick()`) | `easy_service_app()` | Overrides the log level chosen by `svc_infra.app.pick`. |
| `LOG_FORMAT` | Auto (JSON in prod, plain elsewhere) | `easy_service_app()` | Explicit `json` or `plain` format overrides auto-detection. |
| `ENABLE_OBS` | `true` | `EasyAppOptions.from_env()` / `easy_service_app()` | Turns observability instrumentation on/off. |
| `METRICS_PATH` | `None` → falls back to Observability settings | `EasyAppOptions.from_env()` | Use to expose metrics at a non-default path. |
| `OBS_SKIP_PATHS` | `None` → defaults to metrics + health endpoints | `EasyAppOptions.from_env()` | Comma/space-separated list of paths skipped by Prometheus middleware. |
| `CORS_ALLOW_ORIGINS` | `""` (no origins) | `_setup_cors()` | Adds `CORSMiddleware` allow-list when non-empty. |

### SQL helpers (`add_sql_db`, `setup_sql`)

| Variable | Default | Consumed by | Notes |
| --- | --- | --- | --- |
| `SQL_URL` (overridable via `dsn_env`) | _required_ | `add_sql_db()` / `setup_sql()` | Missing value raises `RuntimeError`; point at your primary database URL. |

### Mongo helpers (`add_mongo_db`, `init_mongo`)

| Variable | Default | Consumed by | Notes |
| --- | --- | --- | --- |
| `MONGO_URL` / `MONGODB_URL` | `mongodb://localhost:27017` | `MongoSettings`, `add_mongo_db()` | Primary Mongo connection string; `_FILE` suffix or `MONGO_URL_FILE` allow secret mounts. |
| `MONGO_DB` / `MONGODB_DB` / `MONGO_DATABASE` | unset (optional) | `get_mongo_dbname_from_env()` | When set, verified against the connected database name. |
| `MONGO_APPNAME` | `svc-infra` | `MongoSettings` | Sets the Mongo client `appname`. |
| `MONGO_MIN_POOL` | `0` | `MongoSettings` | Minimum Motor/Mongo client pool size. |
| `MONGO_MAX_POOL` | `100` | `MongoSettings` | Maximum Motor/Mongo client pool size. |
| `MONGO_URL_FILE` | unset | `get_mongo_url_from_env()` | Alternate secret file path when not using `_FILE` suffix envs. |
| `/run/secrets/mongo_url` | unset | `get_mongo_url_from_env()` | Auto-mounted Docker/K8s secret fallback for the URL. |

### Auth settings (`get_auth_settings` → `AuthSettings`)

Pydantic loads these with the `AUTH_` prefix and `__` as the nested delimiter.

| Variable | Default | Consumed by | Notes |
| --- | --- | --- | --- |
| `AUTH_JWT__SECRET` | _required when JWT auth enabled_ | `AuthSettings.jwt.secret` | Primary HS256 signing secret. |
| `AUTH_JWT__LIFETIME_SECONDS` | `604800` (7 days) | `AuthSettings.jwt.lifetime_seconds` | Adjusts refresh token lifetime. |
| `AUTH_JWT__OLD_SECRETS__*` | `[]` | `AuthSettings.jwt.old_secrets` | Accepted legacy secrets during rotation. |
| `AUTH_PASSWORD_CLIENTS__{n}__CLIENT_ID` | `[]` | `AuthSettings.password_clients[*].client_id` | Register password clients (list entries indexed by `{n}`). |
| `AUTH_PASSWORD_CLIENTS__{n}__CLIENT_SECRET` | `[]` | `AuthSettings.password_clients[*].client_secret` | Secret per password client. |
| `AUTH_REQUIRE_CLIENT_SECRET_ON_PASSWORD_LOGIN` | `false` | `AuthSettings.require_client_secret_on_password_login` | Enforces client secret on password grant. |
| `AUTH_MFA_DEFAULT_ENABLED_FOR_NEW_USERS` | `false` | `AuthSettings.mfa_default_enabled_for_new_users` | Enable TOTP by default on signup. |
| `AUTH_MFA_ENFORCE_FOR_ALL_USERS` | `false` | `AuthSettings.mfa_enforce_for_all_users` | Force MFA globally. |
| `AUTH_MFA_ENFORCE_FOR_TENANTS` | `[]` | `AuthSettings.mfa_enforce_for_tenants` | Tenant allow-list requiring MFA. |
| `AUTH_MFA_ISSUER` | `"svc-infra"` | `AuthSettings.mfa_issuer` | Label for TOTP apps. |
| `AUTH_MFA_PRE_TOKEN_LIFETIME_SECONDS` | `300` | `AuthSettings.mfa_pre_token_lifetime_seconds` | Lifespan of MFA pre-token. |
| `AUTH_MFA_RECOVERY_CODES` | `8` | `AuthSettings.mfa_recovery_codes` | Number of recovery codes issued. |
| `AUTH_MFA_RECOVERY_CODE_LENGTH` | `10` | `AuthSettings.mfa_recovery_code_length` | Digits per recovery code. |
| `AUTH_EMAIL_OTP_TTL_SECONDS` | `300` | `AuthSettings.email_otp_ttl_seconds` | Email OTP validity window. |
| `AUTH_EMAIL_OTP_COOLDOWN_SECONDS` | `60` | `AuthSettings.email_otp_cooldown_seconds` | Cooldown between OTP sends. |
| `AUTH_EMAIL_OTP_ATTEMPTS` | `5` | `AuthSettings.email_otp_attempts` | Maximum OTP attempts before lock. |
| `AUTH_SMTP_HOST` | `None` | `AuthSettings.smtp_host` | SMTP hostname (required for prod email). |
| `AUTH_SMTP_PORT` | `587` | `AuthSettings.smtp_port` | SMTP port. |
| `AUTH_SMTP_USERNAME` | `None` | `AuthSettings.smtp_username` | SMTP username. |
| `AUTH_SMTP_PASSWORD` | `None` | `AuthSettings.smtp_password` | SMTP password/secret. |
| `AUTH_SMTP_FROM` | `None` | `AuthSettings.smtp_from` | Default From address. |
| `AUTH_AUTO_VERIFY_IN_DEV` | `true` | `AuthSettings.auto_verify_in_dev` | Auto-confirms accounts outside prod. |
| `AUTH_GOOGLE_CLIENT_ID` | `None` | `AuthSettings.google_client_id` | Built-in Google OAuth client ID. |
| `AUTH_GOOGLE_CLIENT_SECRET` | `None` | `AuthSettings.google_client_secret` | Built-in Google OAuth secret. |
| `AUTH_GITHUB_CLIENT_ID` | `None` | `AuthSettings.github_client_id` | GitHub OAuth client ID. |
| `AUTH_GITHUB_CLIENT_SECRET` | `None` | `AuthSettings.github_client_secret` | GitHub OAuth secret. |
| `AUTH_MS_CLIENT_ID` | `None` | `AuthSettings.ms_client_id` | Microsoft OAuth client ID. |
| `AUTH_MS_CLIENT_SECRET` | `None` | `AuthSettings.ms_client_secret` | Microsoft OAuth secret. |
| `AUTH_MS_TENANT` | `None` | `AuthSettings.ms_tenant` | Microsoft tenant ID. |
| `AUTH_LI_CLIENT_ID` | `None` | `AuthSettings.li_client_id` | LinkedIn OAuth client ID. |
| `AUTH_LI_CLIENT_SECRET` | `None` | `AuthSettings.li_client_secret` | LinkedIn OAuth secret. |
| `AUTH_OIDC_PROVIDERS__{n}__NAME` | `[]` | `AuthSettings.oidc_providers[*].name` | Custom OIDC providers (list entries indexed by `{n}`). |
| `AUTH_OIDC_PROVIDERS__{n}__ISSUER` | `[]` | `AuthSettings.oidc_providers[*].issuer` | OIDC issuer URL. |
| `AUTH_OIDC_PROVIDERS__{n}__CLIENT_ID` | `[]` | `AuthSettings.oidc_providers[*].client_id` | OIDC client ID. |
| `AUTH_OIDC_PROVIDERS__{n}__CLIENT_SECRET` | `[]` | `AuthSettings.oidc_providers[*].client_secret` | OIDC client secret. |
| `AUTH_OIDC_PROVIDERS__{n}__SCOPE` | `"openid email profile"` | `AuthSettings.oidc_providers[*].scope` | Additional OIDC scopes. |
| `AUTH_POST_LOGIN_REDIRECT` | `http://localhost:3000/app` | `AuthSettings.post_login_redirect` | Default redirect after login. |
| `AUTH_REDIRECT_ALLOW_HOSTS_RAW` | `"localhost,127.0.0.1"` | `AuthSettings.redirect_allow_hosts_raw` | CSV/JSON allow-list for redirects. |
| `AUTH_SESSION_COOKIE_NAME` | `"svc_session"` | `AuthSettings.session_cookie_name` | Session cookie key. |
| `AUTH_AUTH_COOKIE_NAME` | `"svc_auth"` | `AuthSettings.auth_cookie_name` | Auth cookie key. |
| `AUTH_SESSION_COOKIE_SECURE` | `false` | `AuthSettings.session_cookie_secure` | Marks session cookie `Secure`. |
| `AUTH_SESSION_COOKIE_SAMESITE` | `"lax"` | `AuthSettings.session_cookie_samesite` | SameSite policy. |
| `AUTH_SESSION_COOKIE_DOMAIN` | `None` | `AuthSettings.session_cookie_domain` | Explicit cookie domain. |
| `AUTH_SESSION_COOKIE_MAX_AGE_SECONDS` | `14400` (4 hours) | `AuthSettings.session_cookie_max_age_seconds` | Session cookie lifetime. |

## Jobs helpers

| Variable | Default | Consumed by | Notes |
| --- | --- | --- | --- |
| `JOBS_DRIVER` | `memory` | `JobsConfig`, `easy_jobs()` | Choose `redis` to activate Redis-backed queue. |
| `REDIS_URL` | `redis://localhost:6379/0` | `easy_jobs()` (Redis driver) | Redis connection string when `JOBS_DRIVER=redis`. |
| `JOBS_SCHEDULE_JSON` | unset | `schedule_from_env()` | JSON array of scheduler tasks (name, interval_seconds, target). |

## Observability helpers

| Variable | Default | Consumed by | Notes |
| --- | --- | --- | --- |
| `METRICS_ENABLED` | `true` | `ObservabilitySettings` | Gate for Prometheus middleware registration. |
| `METRICS_PATH` | `/metrics` | `ObservabilitySettings`, `add_observability()` | Metrics endpoint path. |
| `METRICS_DEFAULT_BUCKETS` | `0.005,0.01,0.025,0.05,0.1,0.25,0.5,1.0,2.0,5.0,10.0` | `ObservabilitySettings` | Histogram buckets for request latency. |
| `SVC_INFRA_DISABLE_PROMETHEUS` | unset (`"1"` disables) | `metrics.asgi` | Skip Prometheus setup when toggled. |
| `SVC_INFRA_RATE_WINDOW` | unset | `cloud_dash.push_dashboards_from_pkg()` | Overrides `$__rate_interval` in dashboards. |
| `SVC_INFRA_DASHBOARD_REFRESH` | `5s` | `cloud_dash.push_dashboards_from_pkg()` | Grafana dashboard auto-refresh interval. |
| `SVC_INFRA_DASHBOARD_RANGE` | `now-6h` | `cloud_dash.push_dashboards_from_pkg()` | Default Grafana time range start. |

## Security helpers

The primitives under `svc_infra.security` rely on configuration objects passed from application code; they do not read environment variables directly beyond the shared `AuthSettings` listed above.

## Webhook helpers

Current webhook helpers (`fastapi.require_signature`, `InMemoryWebhookSubscriptions`, `WebhookService`) rely on dependency injection for secrets and stores and do not read environment variables directly.
