#!/usr/bin/env bash
# Helper script to run svc-infra SQL commands with .env loaded
# This script ensures migrations are created in the examples/ directory

set -e

# Get the directory where this script is located (examples/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the examples directory
cd "$SCRIPT_DIR"

# Load .env file
if [ -f .env ]; then
    echo "Loading environment from .env..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
else
    echo "Warning: .env file not found in $SCRIPT_DIR"
fi

# Set PROJECT_ROOT to examples directory so migrations go here, not in git root
export PROJECT_ROOT="$SCRIPT_DIR"

echo "✓ Project root: $PROJECT_ROOT"
echo "✓ SQL_URL: ${SQL_URL:-<not set>}"

# Run the SQL command with all arguments passed through
# Use poetry run from examples directory (which has svc-infra as a dependency)
poetry run python -m svc_infra.cli sql "$@"
