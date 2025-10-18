SHELL := /bin/bash

.PHONY: accept compose_up wait seed down pytest_accept unit unitv clean clean-acceptance

compose_up:
	@echo "[accept] Starting test stack..."
	docker compose -f docker-compose.test.yml up -d --remove-orphans --quiet-pull

wait:
	@echo "[accept] Waiting for API to become ready..."
	# Wait up to ~60s for /ping to return 200
	end=$$(($(shell date +%s) + 60)); \
	while [ $$(date +%s) -lt $$end ]; do \
		if curl -fsS http://localhost:8000/ping >/dev/null || curl -fsS http://127.0.0.1:8000/ping >/dev/null; then \
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

accept: compose_up wait seed pytest_accept
	@echo "[accept] Acceptance complete"

down:
	@echo "[accept] Tearing down test stack..."
	docker compose -f docker-compose.test.yml down -v --remove-orphans

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

clean-acceptance:
	@echo "[clean] Tearing down acceptance stack and removing artifacts"
	- docker compose -f docker-compose.test.yml down -v --remove-orphans || true
	- docker network rm svc-infra-accept || true
	# No persistent artifacts expected from acceptance. Extend as needed.
