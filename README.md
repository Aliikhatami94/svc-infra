# svc-infra

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)

Infrastructure library for building and deploying production-ready services with FastAPI, SQLAlchemy, authentication, observability, and more.

## Features

### **Core Infrastructure**
- **FastAPI Integration**: Pre-configured FastAPI application with middleware, error handling, and routing
- **Database Support**: Multiple database backends (PostgreSQL, MySQL, SQLite, SQL Server, Snowflake, DuckDB)
- **Authentication**: OAuth integration with FastAPI-Users
- **CLI Tools**: Command-line interface for database migrations, scaffolding, and observability
- **Observability**: OpenTelemetry tracing, Prometheus metrics, and Grafana dashboards
- **MCP Integration**: Model Context Protocol support for AI integrations

### **Database Management**
- **SQL**: SQLAlchemy 2.0 with async support
- **Migrations**: Alembic integration for database schema management
- **NoSQL**: MongoDB support with Motor
- **Multi-database**: Support for multiple database connections

### **Authentication & Authorization**
- OAuth providers integration
- User management with FastAPI-Users
- Secure password hashing with bcrypt
- Email validation
- JWT token handling

### **Observability**
- OpenTelemetry distributed tracing
- Prometheus metrics collection
- Grafana dashboard templates
- Request/response logging
- Error tracking and monitoring

## Installation

### Basic Installation

```bash
pip install svc-infra
```

### With Database Extras

```bash
# PostgreSQL (v3)
pip install svc-infra[pg]

# PostgreSQL (v2)
pip install svc-infra[pg2]

# SQLite
pip install svc-infra[sqlite]

# MySQL
pip install svc-infra[mysql]

# SQL Server
pip install svc-infra[mssql]

# Snowflake
pip install svc-infra[snowflake]

# DuckDB
pip install svc-infra[duckdb]

# All databases
pip install svc-infra[pg,sqlite,mysql,mssql,snowflake,duckdb]
```

### With Metrics Support

```bash
pip install svc-infra[metrics]
```

## Quick Start

### 1. Create a FastAPI Application

```python
from fastapi import FastAPI
from svc_infra.api.fastapi import create_app
from svc_infra.app.settings import AppSettings

# Create your app settings
settings = AppSettings()

# Create the FastAPI app with svc-infra
app = create_app(settings)

@app.get("/")
async def root():
    return {"message": "Hello from svc-infra!"}
```

### 2. Database Setup

```python
from svc_infra.db.sql import setup_database

# Setup database connection
await setup_database(settings.database_url)
```

### 3. Add Authentication

```python
from svc_infra.auth import add_auth

# Add authentication to your FastAPI app
add_auth(app, settings)
```

### 4. CLI Usage

The library provides a CLI for common tasks:

```bash
# Database migrations
svc-infra alembic init
svc-infra alembic migrate "Initial migration"
svc-infra alembic upgrade

# Generate database scaffolding
svc-infra sql scaffold --table users --model User

# Observability setup
svc-infra obs setup
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db

# Authentication
SECRET_KEY=your-secret-key
OAUTH_CLIENT_ID=your-oauth-client-id
OAUTH_CLIENT_SECRET=your-oauth-client-secret

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
PROMETHEUS_PORT=8000
```

### Settings Class

```python
from svc_infra.app.settings import AppSettings

settings = AppSettings(
    database_url="postgresql+asyncpg://user:pass@localhost/db",
    secret_key="your-secret-key",
    debug=True
)
```

## Project Structure

```
svc-infra/
├── src/svc_infra/
│   ├── api/           # FastAPI integration and middleware
│   ├── app/           # Application settings and configuration
│   ├── auth/          # Authentication and authorization
│   ├── cli/           # Command-line interface
│   ├── db/            # Database connections and utilities
│   ├── mcp/           # Model Context Protocol integration
│   └── observability/ # Monitoring, metrics, and tracing
├── tests/             # Test suite
└── pyproject.toml     # Project configuration
```

## Database Support

### Supported Databases

| Database | Driver | Extra | Connection String Example |
|----------|--------|-------|--------------------------|
| PostgreSQL (v3) | asyncpg/psycopg | `[pg]` | `postgresql+asyncpg://user:pass@host/db` |
| PostgreSQL (v2) | psycopg2 | `[pg2]` | `postgresql://user:pass@host/db` |
| SQLite | aiosqlite | `[sqlite]` | `sqlite+aiosqlite:///path/to/db.sqlite` |
| MySQL | pymysql | `[mysql]` | `mysql+pymysql://user:pass@host/db` |
| SQL Server | pyodbc | `[mssql]` | `mssql+pyodbc://user:pass@host/db` |
| Snowflake | snowflake | `[snowflake]` | `snowflake://user:pass@account/db` |
| DuckDB | duckdb | `[duckdb]` | `duckdb:///path/to/db.duckdb` |

## Authentication

### OAuth Providers

The library supports multiple OAuth providers through FastAPI-Users:

- Google
- GitHub
- Microsoft
- Discord
- And more...

### Example OAuth Setup

```python
from svc_infra.auth.providers import setup_oauth_providers

oauth_providers = setup_oauth_providers({
    "google": {
        "client_id": "your-google-client-id",
        "client_secret": "your-google-client-secret"
    }
})
```

## Observability

### Tracing

OpenTelemetry tracing is automatically configured for:
- FastAPI requests
- SQLAlchemy database operations
- HTTP client requests (httpx, requests)

### Metrics

Prometheus metrics are collected for:
- Request duration and count
- Database query performance
- Custom business metrics

### Dashboards

Pre-built Grafana dashboards are included for:
- API performance monitoring
- Database metrics
- System health checks

## CLI Commands

| Command | Description |
|---------|-------------|
| `svc-infra alembic init` | Initialize Alembic migrations |
| `svc-infra alembic migrate <message>` | Create new migration |
| `svc-infra alembic upgrade` | Apply migrations |
| `svc-infra sql scaffold` | Generate database models and schemas |
| `svc-infra obs setup` | Setup observability stack |

## Development

### Prerequisites

- Python 3.11+
- Poetry (for dependency management)

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/your-org/svc-infra.git
cd svc-infra

# Install dependencies
poetry install --all-extras

# Install pre-commit hooks
pre-commit install

# Run tests
poetry run pytest
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=svc_infra

# Run specific test file
poetry run pytest tests/auth/test_providers.py
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Run the test suite (`poetry run pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes in each version.

## Support

-  **Email**: aliikhatami94@gmail.com
-  **Issues**: [GitHub Issues](https://github.com/your-org/svc-infra/issues)
-  **Documentation**: [GitHub README](https://github.com/your-org/svc-infra#readme)

---

**Built️ for production-ready Python services**
