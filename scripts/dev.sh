#!/usr/bin/env bash
# CivicPulse AI - start the backend and frontend together (macOS / Linux).
# Run from the repository root:   bash scripts/dev.sh      (Ctrl+C stops both)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting backend on http://localhost:8000 (API docs: /docs)..."
(cd "$ROOT/backend" && .venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT INT TERM

echo "Starting frontend on http://localhost:3000 ..."
cd "$ROOT/frontend"
npm run dev
