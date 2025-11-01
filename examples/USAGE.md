# How to Use This Example

This example demonstrates how to build a production-ready service using svc-infra.

## 🎯 Purpose

This is a **learning template** that shows:
- How to structure a service using svc-infra
- How to configure logging, versioning, and metadata
- How to enable features (DB, auth, payments, observability)
- How to extend with custom logic

## 📦 Two Ways to Use This Example

### 1️⃣ As a Template (Copy to Your Workspace)

**Best for:** Starting a new project

```bash
# Copy this directory to your workspace
cp -r /path/to/svc-infra/examples ~/my-projects/my-api

cd ~/my-projects/my-api

# Update pyproject.toml to use published svc-infra
# Change: svc-infra = { path = "../../", develop = true }
# To:     svc-infra = "^0.1.0"

# Install and run
poetry install
make run
```

**Then customize:**
- Update service name in `main.py` (ServiceInfo)
- Update package names (`svc_infra_template` → `your_service`)
- Enable features you need (uncomment in main.py)
- Add your own routes in `api/v1/routes.py`

### 2️⃣ Run Directly (Inside svc-infra Repo)

**Best for:** Learning and experimenting

```bash
# From svc-infra root
cd examples

# Install (uses local svc-infra via develop = true)
poetry install

# Run
make run

# Visit http://localhost:8000/docs
```

**Benefits:**
- Uses latest svc-infra code from parent directory
- Changes to svc-infra immediately available
- Good for testing svc-infra features

## 🔧 Configuration

### When Used as Standalone

**pyproject.toml:**
```toml
[tool.poetry.dependencies]
python = ">=3.11,<4.0"
svc-infra = "^0.1.0"  # Fetch from PyPI
```

### When Used Inside svc-infra Repo

**pyproject.toml:**
```toml
[tool.poetry.dependencies]
python = ">=3.11,<4.0"
svc-infra = { path = "../../", develop = true }  # Use local dev version
```

## 📚 Learning Path

1. **Read `main.py`** - 300+ lines of educational comments explaining every feature
2. **Run the example** - See it work with `make run`
3. **Enable features** - Uncomment DB, auth, caching, etc. in main.py
4. **Add routes** - Extend `api/v1/routes.py` with your own endpoints
5. **Customize** - Adapt to your team's needs

## 🛠️ Available Commands

```bash
make help     # Show all commands
make install  # Install dependencies
make run      # Start development server
make clean    # Clean cache files
make update   # Update dependencies
```

## 🌐 Endpoints

Once running, visit:
- **API Docs**: http://localhost:8000/docs
- **OpenAPI**: http://localhost:8000/openapi.json
- **Health**: http://localhost:8000/ping
- **v1 Routes**: http://localhost:8000/v1/ping, /v1/status

## 💡 Next Steps

After understanding this example:
1. Copy it to your workspace
2. Rename package from `svc_infra_template` to your service name
3. Update service metadata in `main.py`
4. Enable features you need (DB, auth, etc.)
5. Build your API!

See the main svc-infra documentation for detailed feature guides.
