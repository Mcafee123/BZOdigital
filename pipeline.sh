#!/usr/bin/env bash
#
# Start the nupla pipeline (stage I): FastAPI on :7100 serving the API and the
# static UI from src/nupla/pipeline/static/. Backend and frontend share one
# process — there is no separate frontend dev server.
#
# Usage:
#   ./start-pipeline.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Syncing deps (uv sync)"
(cd "$ROOT_DIR" && uv sync)

echo "==> Starting nupla pipeline on http://localhost:7100"
exec uv run --project "$ROOT_DIR" nupla serve
