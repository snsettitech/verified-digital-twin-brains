#!/bin/bash
# scripts/stop-hook.sh
# Orchestrates quality and governance gates. Auto-commits on success.

set -e

# Configuration
SKIP_AI_GATE=${SKIP_AI_GATE:-false}

if [ "$SKIP_AI_GATE" = "true" ]; then
    echo "⚠️  AI Gate SKIPPED (SKIP_AI_GATE=true)"
    exit 0
fi

echo "🚀 AI Stop-Hook: Starting verification pipeline..."

# 1. Governance Gate (Static Analysis)
python scripts/ai-verify-governance.py
if [ $? -ne 0 ]; then
    echo "AI_GATE_FAILURE: Governance"
    exit 1
fi

# 2. Quality Gate (Lint, Type, Test)
bash scripts/ai-verify-quality.sh 
if [ $? -ne 0 ]; then
    echo "AI_GATE_FAILURE: Quality"
    exit 1
fi

# 3. Finalize
echo "🎉 All gates passed! Finalizing change..."

# Only commit if there are changes
if git diff-index --quiet HEAD --; then
    echo "No changes to commit."
else
    git add -A
    git commit -m "AI: verified change passing quality + governance checks"
    echo "✅ Changes committed successfully."
fi

echo ""
echo "Next steps:"
echo "  git push origin main"
