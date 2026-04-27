#!/usr/bin/env bash
#
# Start the nupla diff-viewer app (stage IV): FastAPI BFF on :8001 + Vite on
# :5173. Vite proxies /api/* to the backend. Open http://localhost:5173.
#
# Usage:
#   ./start-app.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$ROOT_DIR/src/nupla/app/scripts/dev.sh" "$@"
