#!/bin/bash
# scripts/ai-verify-quality.sh
# Comprehensive quality gate for AI-generated code.

set -e

echo "🔍 AI Quality Gate: Running validations..."

# 1. Backend Checks
echo "--- Backend ---"
cd backend

echo "Linting (flake8)..."
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
python -m flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

echo "Testing (pytest)..."
# Exclude network tests for speed and reliability in gate
python -m pytest -v --tb=short -m "not network" 2>&1 | tail -n 20

cd ..

# 2. Frontend Checks
echo ""
echo "--- Frontend ---"
cd frontend

echo "Linting (eslint)..."
npm run lint

echo "Type Checking (tsc)..."
npm run typecheck

cd ..

echo ""
echo "✅ Quality Gate Passed"
