#!/usr/bin/env bash
set -euo pipefail

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
if [[ -z "$PYTHON" ]]; then
  echo "Error: Python is required but not found."
  exit 1
fi

"$PYTHON" "$(dirname "$0")/setup.py"
