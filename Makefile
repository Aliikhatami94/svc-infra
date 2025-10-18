SHELL := /bin/bash
RMI ?= all

.PHONY: accept compose_up wait seed down pytest_accept unit unitv clean

compose_up:
	@echo "[accept] Starting test stack..."
	docker compose -f docker-compose.test.yml up -d --remove-orphans --quiet-pull

wait:
	@echo "[accept] Waiting for API to become ready (inside api container)..."
		@ : "Poll the API from inside the running api container to avoid host/port quirks"; \
		end=$$(($(shell date +%s) + 60)); \
		while [ $$(date +%s) -lt $$end ]; do \
			if docker compose -f docker-compose.test.yml exec -T api \
				python -c "import sys,urllib.request; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/ping', timeout=2).status==200 else sys.exit(1)" >/dev/null 2>&1; then \
				echo "[accept] API is ready"; \
				exit 0; \
			fi; \
			sleep 2; \
		done; \
		echo "[accept] Timeout waiting for API"; \
		(docker compose -f docker-compose.test.yml logs --no-color api | tail -n 120 || true); \
		exit 1

seed:
	@echo "[accept] Seeding acceptance data (noop for now)"
	# Placeholder: hook DB migrations/seed via CLI here if needed

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
