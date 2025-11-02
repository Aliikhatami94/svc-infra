# Quick Reference - svc-infra-template

## 🏃 Running the Example

```bash
cd svc-infra/examples
poetry install
cp .env.example .env
make run
# Visit: http://localhost:8001/docs
```

## 📝 Key Configuration

```bash
# In .env file:
APP_ENV=local
API_PORT=8001
SQL_URL=sqlite+aiosqlite:///./svc_infra_template.db
# REDIS_URL=redis://localhost:6379/0
METRICS_ENABLED=true
```

## 🔑 Key Files

- `main.py` - **START HERE** - Explains everything
- `settings.py` - Type-safe configuration
- `.env.example` - All options

## 💡 What's Different

This uses `setup_service_api` (not `easy_service_app`) to show:
- Explicit setup for full control
- Feature toggles via environment
- Production-ready patterns

Read `main.py` for details!
