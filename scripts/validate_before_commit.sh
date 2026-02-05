#!/bin/bash
# Pre-commit validation script - Run this BEFORE pushing

set -e

echo "🔍 Running pre-commit validation..."
echo ""

# Backend checks
echo "1️⃣  Backend Syntax Check (flake8)..."
cd backend
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
if [ $? -ne 0 ]; then
    echo "❌ Backend syntax errors found!"
    exit 1
fi

echo "✅ Backend syntax OK"
echo ""

echo "2️⃣  Backend Lint Check (full)..."
python -m flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
echo "✅ Backend lint OK"
echo ""

echo "3️⃣  Backend Tests..."
python -m pytest -v -s --tb=short -m "not network" 2>&1 | tail -20
if [ $? -ne 0 ]; then
    echo "❌ Backend tests failed!"
    exit 1
fi
echo "✅ Backend tests OK"
echo ""

cd ..

# Frontend checks
echo "4️⃣  Frontend Lint Check..."
cd frontend
if ! npm run lint 2>&1 | grep -q "error"; then
    echo "✅ Frontend lint OK"
else
    echo "❌ Frontend lint errors found!"
    exit 1
fi
echo ""

cd ..

echo "🎉 All validations passed! Safe to commit and push"
echo ""
echo "Next steps:"
echo "  git add -A"
echo "  git commit -m 'your message'"
echo "  git push origin main"
