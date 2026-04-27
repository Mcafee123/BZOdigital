#!/usr/bin/env bash
#
# Start nupla-app locally: FastAPI on :8001 + Vite on :5173.
# Vite proxies /api/* to the backend. Open http://localhost:5173.
#
# Usage:
#   ./scripts/dev.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$APP_DIR/web"

cleanup() {
  trap - INT TERM EXIT
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> Syncing backend deps (uv sync)"
(cd "$APP_DIR" && uv sync)

if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  echo "==> Installing frontend deps (npm install)"
  (cd "$WEB_DIR" && npm install)
fi

echo "==> Starting FastAPI on http://localhost:8001"
(cd "$APP_DIR" && uv run uvicorn nupla.app.server:app --reload --port 8001) &
BACKEND_PID=$!

echo "==> Starting Vite on http://localhost:5173"
(cd "$WEB_DIR" && npm run dev) &
FRONTEND_PID=$!

echo
echo "Backend PID: $BACKEND_PID  |  Frontend PID: $FRONTEND_PID"
echo "Open http://localhost:5173 — Ctrl+C to stop both."
echo

wait -n "$BACKEND_PID" "$FRONTEND_PID"
