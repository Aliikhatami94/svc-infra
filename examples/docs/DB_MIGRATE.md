# db-migrate.sh

Helper script to run svc-infra SQL migrations with environment variables loaded from `.env`.

## Purpose

This script:
1. Loads environment variables from `.env` file
2. Sets `PROJECT_ROOT` to ensure migrations are created in `examples/` directory
3. Runs svc-infra CLI SQL commands with proper Poetry environment

## Usage

```bash
# Setup Alembic and create initial migration
./db-migrate.sh setup-and-migrate \
  --discover-packages=svc_infra_template.db.models \
  --no-with-payments

# Create a new migration
./db-migrate.sh revision --message "add new field" --autogenerate

# Run migrations
./db-migrate.sh upgrade head

# Check current migration status
./db-migrate.sh current

# View migration history
./db-migrate.sh history

# Rollback one migration
./db-migrate.sh downgrade -1
```

## Important Notes

### Running Inside svc-infra Repository

When running migrations inside the svc-infra repository (as opposed to a copied standalone project), the Alembic env.py auto-discovery may include svc-infra's internal models (billing, payments, etc.), even with `--no-with-payments` and `--discover-packages` flags.

**This is because** the generated `migrations/env.py` scans all Python packages in the project root and adds them to discovery.

### Solutions

**Option 1: Use create_tables.py (Recommended for examples)**
```bash
poetry run python create_tables.py
```
- Simpler, no migration history
- Perfect for examples and local development
- No auto-discovery issues

**Option 2: Copy template outside svc-infra repo**
```bash
cp -r svc-infra/examples ~/my-project
cd ~/my-project
# Update pyproject.toml to use published svc-infra version
# Then migrations will work correctly
```

## Environment Variables Required

The script loads these from `.env`:

- `SQL_URL` - Database connection string (required)
- `APP_ENV` - Application environment (optional, default: local)
- Other database-related vars as needed

## Files Created

When you run migrations, these files are created in the `examples/` directory:

- `alembic.ini` - Alembic configuration
- `migrations/` - Directory containing:
  - `env.py` - Alembic environment configuration
  - `script.py.mako` - Template for new migrations
  - `versions/` - Individual migration files

## Troubleshooting

### "No module named 'svc_infra'"
The script uses Poetry from the examples directory. Make sure you've run:
```bash
poetry install
```

### "SQL_URL not set"
Make sure you have a `.env` file with `SQL_URL` defined:
```bash
SQL_URL=sqlite+aiosqlite:///./app.db
```

### Migrations include svc-infra internal models
This happens when running inside the svc-infra repository. Use `create_tables.py` instead, or copy the template to a standalone directory.

## See Also

- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [docs/DATABASE.md](docs/DATABASE.md) - Complete database documentation
- [docs/CLI.md](docs/CLI.md) - CLI command reference
