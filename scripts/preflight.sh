#!/bin/bash
# Preflight Script - Run this before pushing to ensure CI will pass
# Usage: ./scripts/preflight.sh

set -e  # Exit on first error

echo "=========================================="
echo "🚀 PREFLIGHT CHECK - verified-digital-twin-brain"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get repo root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo ""
echo "📁 Repo root: $REPO_ROOT"

# ==========================================
# FRONTEND PREFLIGHT
# ==========================================
echo ""
echo "${YELLOW}=========================================="
echo "📦 FRONTEND PREFLIGHT"
echo "==========================================${NC}"

cd "$REPO_ROOT/frontend"

echo "→ Installing dependencies (npm ci)..."
npm ci --silent

echo "→ Running lint..."
npm run lint

echo "→ Running typecheck..."
npm run typecheck

echo "→ Running build..."
npm run build

echo "${GREEN}✅ Frontend preflight passed!${NC}"

# ==========================================
# BACKEND PREFLIGHT
# ==========================================
echo ""
echo "${YELLOW}=========================================="
echo "🐍 BACKEND PREFLIGHT"
echo "==========================================${NC}"

cd "$REPO_ROOT/backend"

echo "→ Installing dependencies..."
pip install -r requirements.txt -q

echo "→ Running flake8 (syntax errors only)..."
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=.venv,venv,env,__pycache__,.git

echo "→ Running tests..."
pytest -v --tb=short

echo "${GREEN}✅ Backend preflight passed!${NC}"

# ==========================================
# FINAL CHECK
# ==========================================
echo ""
echo "${GREEN}=========================================="
echo "✅ ALL PREFLIGHT CHECKS PASSED!"
echo "   Safe to push to GitHub."
echo "==========================================${NC}"
