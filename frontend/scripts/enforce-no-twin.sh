#!/bin/bash
# ============================================================================
# Enforce Zero "twin" in UI Copy - Phase 3 Testing
# ============================================================================
# This script fails CI if any user-facing UI contains the word "twin"
# Internal identifiers like twin_id are allowed.
# ============================================================================

set -e

echo "🔍 Checking for 'twin' in user-facing UI copy..."

# Files to check
APP_FILES="frontend/app"
COMPONENTS_FILES="frontend/components"
LIB_FILES="frontend/lib"

# Exclude patterns (internal identifiers, file paths with twin_id, etc.)
EXCLUDE_PATTERN='twin_id|twinId|/twins/|/twin/|twin\.id|\.twin\b'

# Function to check for twin occurrences
check_for_twin() {
    local dir=$1
    local label=$2
    
    echo ""
    echo "📁 Checking $label..."
    
    # Find occurrences excluding allowed patterns
    # Using grep -r to search recursively
    if grep -ri "twin" "$dir" --include="*.tsx" --include="*.ts" --include="*.jsx" --include="*.js" 2>/dev/null | grep -viE "$EXCLUDE_PATTERN" | grep -v "node_modules" | head -20 > /tmp/twin_violations_$label.txt; then
        local count=$(wc -l < /tmp/twin_violations_$label.txt)
        if [ "$count" -gt 0 ]; then
            echo "❌ FOUND $count violations in $label:"
            cat /tmp/twin_violations_$label.txt
            return 1
        fi
    fi
    
    echo "✅ No violations found in $label"
    return 0
}

# Check navigation config specifically
echo ""
echo "📁 Checking navigation config..."
if grep -i "twin" frontend/lib/navigation/config.ts 2>/dev/null | grep -vi "//.*twin" | head -10 > /tmp/twin_violations_nav.txt; then
    count=$(wc -l < /tmp/twin_violations_nav.txt)
    if [ "$count" -gt 0 ]; then
        echo "❌ FOUND $count violations in navigation config:"
        cat /tmp/twin_violations_nav.txt
        NAV_VIOLATIONS=1
    fi
else
    echo "✅ No violations found in navigation config"
    NAV_VIOLATIONS=0
fi

# Run checks
APP_VIOLATIONS=0
COMPONENTS_VIOLATIONS=0
LIB_VIOLATIONS=0

if ! check_for_twin "$APP_FILES" "app"; then
    APP_VIOLATIONS=1
fi

if ! check_for_twin "$COMPONENTS_FILES" "components"; then
    COMPONENTS_VIOLATIONS=1
fi

if ! check_for_twin "$LIB_FILES" "lib"; then
    LIB_VIOLATIONS=1
fi

# Summary
echo ""
echo "========================================"
echo "SUMMARY"
echo "========================================"

TOTAL_VIOLATIONS=$((APP_VIOLATIONS + COMPONENTS_VIOLATIONS + LIB_VIOLATIONS + NAV_VIOLATIONS))

if [ "$TOTAL_VIOLATIONS" -gt 0 ]; then
    echo "❌ FAILED: Found $TOTAL_VIOLATIONS violation(s)"
    echo ""
    echo "The word 'twin' must not appear in user-facing UI copy."
    echo "Internal identifiers like 'twin_id', 'twinId', '/twins/' are allowed."
    exit 1
else
    echo "✅ PASSED: No 'twin' violations found in UI copy"
    exit 0
fi
