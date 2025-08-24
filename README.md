# svc-infra

Infrastructure for building and deploying prod-ready applications:
- **FastAPI** app scaffolding with versioned mounting and uniform error handling
- **SQLAlchemy** async DB integration + Alembic CLI
- **Auth** via fastapi-users (session/refresh/OAuth)
- Simple **CRUD** router generator
- Logging, metrics, tracing, health checks

## Install

```bash
poetry add svc-infra
# or
pip install svc-infra
```
