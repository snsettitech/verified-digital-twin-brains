#!/bin/bash
# Local development helper for Linux/macOS.
# Uses the canonical env files: repo-root `.env` and `frontend/.env.local`.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

ROOT_ENV="$REPO_ROOT/.env"
ROOT_ENV_EXAMPLE="$REPO_ROOT/.env.example"
FRONTEND_ENV="$REPO_ROOT/frontend/.env.local"
FRONTEND_ENV_EXAMPLE="$REPO_ROOT/frontend/.env.example"

if [[ ! -f "$ROOT_ENV" ]]; then
  cp "$ROOT_ENV_EXAMPLE" "$ROOT_ENV"
  echo "[i] Created .env from .env.example. Fill in real backend values before continuing."
fi

if [[ ! -f "$FRONTEND_ENV" ]]; then
  cp "$FRONTEND_ENV_EXAMPLE" "$FRONTEND_ENV"
  echo "[i] Created frontend/.env.local from frontend/.env.example."
fi

backend_activate=""
if [[ -f "$REPO_ROOT/backend/.venv/bin/activate" ]]; then
  backend_activate="$REPO_ROOT/backend/.venv/bin/activate"
elif [[ -f "$REPO_ROOT/backend/venv/bin/activate" ]]; then
  backend_activate="$REPO_ROOT/backend/venv/bin/activate"
fi

cleanup() {
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$REPO_ROOT/backend"
  if [[ -n "$backend_activate" ]]; then
    # shellcheck disable=SC1090
    source "$backend_activate"
  fi
  python -m pip install -r requirements.txt
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

sleep 2

(
  cd "$REPO_ROOT/frontend"
  npm ci
  npm run dev
) &
FRONTEND_PID=$!

echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Swagger:  http://localhost:8000/docs"

wait
