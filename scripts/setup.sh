#!/usr/bin/env bash
# CivicPulse AI - one-time setup for macOS / Linux.
# Run from the repository root:   bash scripts/setup.sh
#
# What it does:
#   1. Checks Node.js and Python are installed
#   2. Creates .env from .env.example (with a random SECRET_KEY) if it doesn't exist
#   3. Creates the backend virtual environment and installs Python packages
#   4. Runs database migrations and seeds the demo user
#   5. Installs frontend npm packages
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

step() { printf "\n\033[36m==> %s\033[0m\n" "$1"; }
fail() { printf "\033[31m  %s\033[0m\n" "$1"; exit 1; }

PYTHON="$(command -v python3 || command -v python || true)"

step "Checking prerequisites"
command -v node >/dev/null || fail "'node' was not found. Install Node.js first (see docs/development.md)."
command -v npm >/dev/null || fail "'npm' was not found."
[ -n "$PYTHON" ] || fail "Python 3.11+ was not found."
echo "  node $(node --version), npm $(npm --version), $($PYTHON --version)"

step "Preparing .env"
if [ -f .env ]; then
  echo "  .env already exists - leaving it unchanged."
else
  SECRET="$($PYTHON -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" .env.example > .env
  echo "  Created .env with a random SECRET_KEY. Check DATABASE_URL in it."
fi

step "Setting up the backend (Python virtual environment)"
cd "$ROOT/backend"
[ -d .venv ] || "$PYTHON" -m venv .venv
PY=".venv/bin/python"
"$PY" -m pip install --upgrade pip --quiet
"$PY" -m pip install -e ".[dev]" --quiet

step "Running database migrations"
"$PY" -m alembic upgrade head || fail "Could not migrate. Is PostgreSQL running and DATABASE_URL correct? See docs/development.md."
"$PY" -m scripts.seed

step "Setting up the frontend (npm packages)"
cd "$ROOT/frontend"
npm install

cd "$ROOT"
printf "\n\033[32mSetup complete!\033[0m\n"
echo "Start both servers with:   bash scripts/dev.sh"
echo "Then open http://localhost:3000  (demo login: demo@civicpulse.example / DemoPass123)"
