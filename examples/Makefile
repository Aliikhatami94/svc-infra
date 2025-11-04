.PHONY: help install setup scaffold run clean shell update test-setup

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with Poetry
	poetry install

setup: install ## Complete project setup (scaffold models + migrations)
	@echo "🚀 Setting up svc-infra template project..."
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env from .env.example..."; \
		cp .env.example .env; \
	fi
	@echo "🏗️  Running scaffolding and migrations..."
	python3 scripts/quick_setup.py
	@echo ""
	@echo "✅ Setup complete! Next steps:"
	@echo "   1. Review .env and configure as needed"
	@echo "   2. Uncomment auth/tenancy/GDPR in src/svc_infra_template/main.py if desired"
	@echo "   3. Run: make run"
	@echo ""

run: ## Start the development server
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env from .env.example..."; \
		cp .env.example .env; \
	fi
	@if [ ! -d "migrations" ]; then \
		echo ""; \
		echo "⚠️  No database migrations found!"; \
		echo "   Run 'make setup' first to scaffold models and initialize the database."; \
		echo ""; \
		exit 1; \
	fi
	./run.sh

clean: ## Clean up cache files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

shell: ## Open a Poetry shell
	poetry shell

update: ## Update dependencies
	poetry update

scaffold: ## Scaffold models only (no migrations)
	@echo "🏗️  Scaffolding models..."
	python3 scripts/scaffold_models.py

test-setup: ## Test duplicate prevention
	@echo "🧪 Testing duplicate prevention..."
	python3 scripts/test_duplicate_prevention.py
