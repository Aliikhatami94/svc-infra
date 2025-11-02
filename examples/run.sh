#!/usr/bin/env bash
# Start the svc-infra template service

set -e

# Get script directory (examples/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load environment variables from .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
  echo "Loading environment variables from $SCRIPT_DIR/.env"
  set -a  # Automatically export all variables
  source "$SCRIPT_DIR/.env"
  set +a  # Stop auto-exporting
fi

# Start the service with Poetry
poetry run uvicorn --app-dir src svc_infra_template.main:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}" \
  --reload \
  --log-level info
