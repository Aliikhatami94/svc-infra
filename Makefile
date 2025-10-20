SHELL := /bin/bash
RMI ?= all

.PHONY: accept compose_up wait seed down pytest_accept unit unitv clean clean-pycache test

compose_up:
	@echo "[accept] Starting test stack..."
	docker compose -f docker-compose.test.yml up -d --remove-orphans --quiet-pull

wait:
	@echo "[accept] Waiting for API to become ready (inside api container)..."
			@ : "Poll the API from inside the running api container to avoid host/port quirks"; \
			end=$$(($(shell date +%s) + 420)); \
		while [ $$(date +%s) -lt $$end ]; do \
			if docker compose -f docker-compose.test.yml exec -T api \
				python -c "import sys,urllib.request; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/ping', timeout=2).status==200 else sys.exit(1)" >/dev/null 2>&1; then \
				echo "[accept] API is ready"; \
				exit 0; \
			fi; \
			sleep 2; \
		done; \
		echo "[accept] Timeout waiting for API"; \
			(docker compose -f docker-compose.test.yml logs --no-color api | tail -n 200 || true); \
		exit 1

seed:
	@echo "[accept] Running CLI migrate/current/downgrade/upgrade (ephemeral sqlite)"
	# Use an ephemeral project root in the container to avoid touching repo files
	docker compose -f docker-compose.test.yml exec -T -e PROJECT_ROOT=/tmp/svc-infra-accept -e SQL_URL=sqlite+aiosqlite:////tmp/svc-infra-accept/accept.db api \
		bash -lc 'rm -rf $$PROJECT_ROOT && mkdir -p $$PROJECT_ROOT && \
		python -m svc_infra.cli sql setup-and-migrate --no-with-payments && \
		python -m svc_infra.cli sql current && \
		python -m svc_infra.cli sql downgrade -- -1 && \
		python -m svc_infra.cli sql upgrade head'
	@echo "[accept] Seeding acceptance data via CLI (no-op)"
		docker compose -f docker-compose.test.yml exec -T api \
			python -m svc_infra.cli sql seed tests.acceptance._seed:acceptance_seed

pytest_accept:
	@echo "[accept] Running acceptance tests in container..."
	docker compose -f docker-compose.test.yml run --rm tester

accept:
	@echo "[accept] Running full acceptance (with auto-clean)"
	@status=0; \
	$(MAKE) compose_up || status=$$?; \
	if [ $$status -eq 0 ]; then \
		$(MAKE) wait || status=$$?; \
	fi; \
	if [ $$status -eq 0 ]; then \
		$(MAKE) seed || status=$$?; \
	fi; \
	if [ $$status -eq 0 ]; then \
		$(MAKE) pytest_accept || status=$$?; \
	fi; \
	echo "[accept] Cleaning acceptance stack (containers, volumes, images)"; \
	docker compose -f docker-compose.test.yml down --rmi $(RMI) -v --remove-orphans || true; \
	if [ $$status -eq 0 ]; then \
		echo "[accept] Acceptance complete"; \
	else \
		echo "[accept] Acceptance failed"; \
	fi; \
	exit $$status

down:
	@echo "[accept] Tearing down test stack..."
	docker compose -f docker-compose.test.yml down --rmi $(RMI) -v --remove-orphans

# --- Unit tests ---
unit:
	@echo "[unit] Running unit tests (quiet)"
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "[unit] Poetry is not installed. Please install Poetry (https://python-poetry.org/docs/#installation)"; \
		exit 2; \
	fi; \
	poetry install --no-interaction --only main,dev >/dev/null 2>&1 || true; \
	poetry run pytest -q tests/unit

unitv:
	@echo "[unit] Running unit tests (verbose)"
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "[unit] Poetry is not installed. Please install Poetry (https://python-poetry.org/docs/#installation)"; \
		exit 2; \
	fi; \
	poetry install --no-interaction --only main,dev >/dev/null 2>&1 || true; \
	poetry run pytest -vv tests/unit

# --- Cleanup helpers ---
clean:
	@echo "[clean] Removing Python caches, build artifacts, and logs"
	rm -rf **/__pycache__ __pycache__ .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info *.log

# Remove only Python __pycache__ directories (recursive)
clean-pycache:
	@echo "[clean] Removing all __pycache__ directories recursively"
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} +

# --- Combined test target ---
test:
	@echo "[test] Running unit and acceptance tests"
	@status=0; \
	$(MAKE) unit || status=$$?; \
	if [ $$status -eq 0 ]; then \
		$(MAKE) accept || status=$$?; \
	fi; \
	if [ $$status -eq 0 ]; then \
		echo "[test] All tests passed"; \
	else \
		echo "[test] Tests failed"; \
	fi; \
	exit $$status
