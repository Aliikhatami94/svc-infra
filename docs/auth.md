# Auth settings

`svc_infra.api.fastapi.auth` wraps FastAPI Users with sensible defaults for sessions, OAuth, MFA, and API keys via `add_auth_users`. Configuration comes from `AuthSettings`, which reads environment variables with the `AUTH_` prefix. 【F:src/svc_infra/api/fastapi/auth/add.py†L240-L321】【F:src/svc_infra/api/fastapi/auth/settings.py†L23-L91】

### Key environment variables

- `AUTH_JWT__SECRET`, `AUTH_JWT__OLD_SECRETS` – rotate signing keys without downtime. 【F:docs/security.md†L63-L70】
- `AUTH_SMTP_HOST`, `AUTH_SMTP_USERNAME`, `AUTH_SMTP_PASSWORD`, `AUTH_SMTP_FROM` – enable SMTP delivery; required in production. 【F:src/svc_infra/api/fastapi/auth/settings.py†L44-L60】【F:src/svc_infra/api/fastapi/auth/sender.py†L33-L59】
- `AUTH_SESSION_COOKIE_SECURE`, `AUTH_SESSION_COOKIE_NAME`, `AUTH_SESSION_COOKIE_SAMESITE` – shape session middleware. 【F:src/svc_infra/api/fastapi/auth/settings.py†L65-L88】【F:src/svc_infra/api/fastapi/auth/add.py†L279-L303】
- `AUTH_PASSWORD_MIN_LENGTH`, `AUTH_PASSWORD_REQUIRE_SYMBOL`, `AUTH_PASSWORD_BREACH_CHECK` – enforce password policy. 【F:docs/security.md†L24-L35】
- `AUTH_MFA_DEFAULT_ENABLED_FOR_NEW_USERS`, `AUTH_MFA_ENFORCE_FOR_ALL_USERS` – adjust MFA enforcement. 【F:src/svc_infra/api/fastapi/auth/settings.py†L32-L40】
