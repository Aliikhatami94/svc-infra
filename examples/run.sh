#!/usr/bin/env bash
# Start the svc-infra template service

set -e

# Load environment variables from .env if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Start the service with Poetry
poetry run uvicorn --app-dir src svc_infra_template.main:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}" \
  --reload \
  --log-level info
