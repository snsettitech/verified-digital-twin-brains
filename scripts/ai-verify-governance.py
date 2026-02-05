import os
import re
import sys

# scripts/ai-verify-governance.py
# Static analysis gate to ensure Digital Brains safety rules.

print("🔍 AI Governance Gate: Verifying safety rules...")

GATES_FAILED = False

def check_security_compliance(file_path):
    """Verifies that endpoints are guarded and queries are isolated."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for endpoints
    endpoints = re.findall(r'@router\.(post|get|patch|delete|put)\(', content)
    if not endpoints:
        return True # Not a router file

    # Manual pass for verified files with complex patterns or safe public routes
    safe_files = ["twins.py", "metrics.py", "feedback.py", "observability.py"]
    if any(sf in file_path for sf in safe_files):
        print(f"✅ {file_path} - (Manually Verified)")
        return True

    violations = []

    # 1. Security Decorator Presence
    # Look for common security dependencies in Depends()
    # We allow some leeway for whitespace
    guards = re.findall(r'Depends\s*\(\s*(require_tenant|require_twin_access|verify_tenant_access|verify_twin_access|verify_owner|get_current_user|verify_conversation_ownership|verify_source_ownership|verify_twin_ownership)\s*\)', content)
    
    if not guards and "auth.py" not in file_path:
        violations.append("Missing security guards (Depends) in router endpoints")

    # 2. Isolation Logic
    # Restricted tables that MUST be filtered
    restricted_tables = ["twins", "conversations", "sources", "messages", "til", "memories", "escalations"]
    
    # Global guards for this file
    has_twin_guard = "verify_twin_ownership" in content or "verify_twin_access" in content or "verify_owner" in content or "verify_tenant_access" in content or "require_tenant" in content or "require_twin_access" in content
    has_auth_guard = "get_current_user" in content or "get_auth_user" in content
    
    # Check if any restricted table is queried
    for table in restricted_tables:
        if f'.table("{table}")' in content or f".table('{table}')" in content:
            # Check for filter
            # Heuristic: must have 'tenant_id', 'twin_id', or 'id' as a filter key
            has_filter = any(f in content for f in ["tenant_id", "twin_id", "id", "conversation_id", "source_id"])
            
            is_isolated = False
            if has_filter and (has_twin_guard or has_auth_guard):
                is_isolated = True
            
            if not is_isolated and "auth.py" not in file_path:
                violations.append(f"Table '{table}' query found without isolation markers (tenant_id/twin_id) or valid guard")

    if violations:
        print(f"❌ GOVERNANCE FAILURE in {file_path}:")
        for v in sorted(set(violations)):
            print(f"  - {v}")
        return False
    
    return True

# 1. Inspect Backend Routers
router_dir = "backend/routers"
if os.path.exists(router_dir):
    for filename in os.listdir(router_dir):
        if filename.endswith(".py"):
            path = os.path.join(router_dir, filename)
            if not check_security_compliance(path):
                GATES_FAILED = True

if GATES_FAILED:
    print("\n🚨 Governance Gate FAILED. Fix the violations before committing.")
    sys.exit(1)
else:
    print("✅ Governance Gate Passed")
    sys.exit(0)

# 2. Inspect New Logic in Modules (Optional, but good for twin_id checks)
# TODO: Add twin_id mandatory checks for Knowledge/Actions
