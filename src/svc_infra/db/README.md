svc_infra.db quickstart

- Env vars
  - DB_DATABASE_URL (preferred) or DATABASE_URL fallback
  - Optional: DB_ECHO, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE, DB_STATEMENT_CACHE_SIZE

- FastAPI wiring
  - from svc_infra.db.integration import attach_db
  - app = FastAPI(); db_engine = attach_db(app)
  - Optional health router: include router from svc_infra.db.integration.routers.health

- Dependencies in routes
  - from svc_infra.db.deps import get_engine, get_session, get_uow
  - Typed deps are also available: EngineDep, SessionDep, UoWDep
  - Use get_uow(request) to operate with repositories inside a transaction

- Repository + UnitOfWork pattern
  - Define models from svc_infra.db.base.Base and UUIDMixin
  - async with UnitOfWork(request.app.state.db_engine) as uow:
      repo = uow.repo(Model); await repo.create(...)

- Alembic migrations (async engine friendly)
  - Initialize: from svc_infra.db.alembic_helpers import init_migrations; init_migrations()
  - Write env.py template: from svc_infra.db.alembic_helpers import write_async_env_template; write_async_env_template()
  - Autogenerate: alembic revision --autogenerate -m "init"
  - Upgrade: alembic upgrade head

- Health check endpoint
  - from svc_infra.db.integration.routers.health import router as db_health_router
  - app.include_router(db_health_router)

- Caching
  - DBEngine accepts an optional cache implementing BaseCache
  - Defaults to NullCache (no-op). InMemoryCache is available for tests/dev in svc_infra.db.cache
  - RedisCache provided in svc_infra.db.redis_cache (or svc_infra.db.cache.redis)
  - Decorator svc_infra.db.redis_cache.cache(ttl=...) helps wrap cacheable calls

- Testing tips
  - Use DB_DATABASE_URL=sqlite+aiosqlite:///:memory:
  - For schema setup in tests, execute CREATE TABLE DDL via AsyncSession or run Alembic migrations

- Troubleshooting
  - postgres:// URLs are normalized to postgresql+asyncpg://
  - For SQLite in-memory, StaticPool is used so multiple sessions share the same DB


Examples

- Copy-pasteable model and repo
  - Model: svc_infra.db.examples.models.Widget (UUIDMixin, TimestampMixin)
  - Repo: svc_infra.db.examples.repo.WidgetRepository (Repository[Widget])

- Sample FastAPI router
  - Import: from svc_infra.db.examples import router as widgets_router
  - Include: app.include_router(widgets_router)
  - Endpoints: GET/POST /examples/widgets

- Migrations quickstart using CLI
  - python -m svc_infra.db init
  - python -m svc_infra.db makemigrations -m "add widgets"
  - python -m svc_infra.db upgrade head
