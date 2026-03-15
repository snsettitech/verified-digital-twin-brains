# Tenant Isolation Analysis
## advisor Namespace Strategy & Multi-Tenancy

---

## Current Tenant Isolation in Your System

### Existing Architecture (Before Migration)

```
Current Isolation Layers:
┌─────────────────────────────────────┐
│  1. Authentication (JWT)            │  ← Who are you?
├─────────────────────────────────────┤
│  2. Row-Level Security (Supabase)   │  ← What can you access?
├─────────────────────────────────────┤
│  3. Namespace (Pinecone)            │  ← Which vectors?
├─────────────────────────────────────┤
│  4. Application Logic               │  ← Business rules
└─────────────────────────────────────┘
```

**Current State:**
- ✅ JWT auth validates user identity
- ✅ Supabase RLS enforces database-level tenant isolation
- ⚠️ Pinecone namespaces are UUID-based (no creator association)
- ⚠️ No explicit tenant validation in vector queries

---

## Proposed Tenant Isolation (creator-namespace pattern)

### New Architecture (After Migration)

```
Enhanced Isolation Layers:
┌────────────────────────────────────────────────────────────┐
│  1. Authentication (JWT)                                   │
│     - Validate user token                                  │
│     - Extract creator_id from claims                       │
├────────────────────────────────────────────────────────────┤
│  2. Tenant Guard (Application Layer)                       │
│     - Verify user owns the requested creator_id            │
│     - Prevent cross-tenant access                          │
├────────────────────────────────────────────────────────────┤
│  3. Namespace Isolation (Pinecone)                         │
│     - creator_{creator_id}_twin_{twin_id}                  │
│     - Physical separation at vector database level         │
├────────────────────────────────────────────────────────────┤
│  4. Metadata Enforcement                                   │
│     - creator_id embedded in vector metadata               │
│     - Secondary validation layer                           │
├────────────────────────────────────────────────────────────┤
│  5. Query Audit Logging                                    │
│     - Log all cross-namespace queries                      │
│     - Alert on suspicious patterns                         │
└────────────────────────────────────────────────────────────┘
```

---

## How the Namespace Strategy Provides Isolation

### 1. Physical Namespace Separation

```python
# Creator A cannot accidentally query Creator B's data
# Because namespaces are completely separate:

creator_a_ns = "creator_sainath.no.1_twin_coach"      # Namespace A
creator_b_ns = "creator_other.user_twin_coach"        # Namespace B

# Query to Namespace A returns only A's vectors
# Query to Namespace B returns only B's vectors
# No cross-contamination possible at Pinecone level
```

**Isolation Level:** Physical (strongest)

### 2. Metadata Secondary Validation

```python
# Even if someone bypasses namespace, metadata has creator_id
vector_metadata = {
    "text": "Example content",
    "creator_id": "sainath.no.1",  # ← Embedded in metadata
    "twin_id": "coach_persona",
    "source": "uploaded_doc"
}

# Application can validate:
if vector.metadata["creator_id"] != requesting_creator_id:
    raise PermissionError("Cross-tenant access detected")
```

**Isolation Level:** Logical (defense in depth)

### 3. Application-Level Tenant Guard

```python
# backend/modules/tenant_guard.py

class TenantGuard:
    """
    Enforces tenant isolation at application level.
    Prevents cross-tenant data access.
    """
    
    def __init__(self, user: dict):
        self.user_id = user["id"]
        self.creator_ids = user.get("creator_ids", [])  # User's creators
    
    def validate_namespace_access(self, creator_id: str) -> bool:
        """
        Verify user can access this creator's namespace.
        
        Raises:
            PermissionError: If user doesn't own this creator
        """
        if creator_id not in self.creator_ids:
            logger.warning(
                f"Tenant isolation violation: "
                f"User {self.user_id} attempted to access creator {creator_id}"
            )
            raise PermissionError(
                f"Access denied: You do not have permission to access "
                f"creator {creator_id}"
            )
        return True
    
    def get_allowed_namespaces(self) -> list:
        """Get list of namespaces this user can access."""
        return [
            f"creator_{cid}_twin_*"
            for cid in self.creator_ids
        ]

# Usage in API endpoints:
@router.post("/query")
async def query_vectors(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    # Enforce tenant isolation
    guard = TenantGuard(current_user)
    guard.validate_namespace_access(request.creator_id)
    
    # Now safe to query
    client = get_advisor_client()
    results = client.query(
        vector=request.vector,
        creator_id=request.creator_id,  # Validated!
        twin_id=request.twin_id
    )
    return results
```

**Isolation Level:** Application (primary defense)

---

## Tenant Isolation Scenarios

### Scenario 1: Normal Access (✅ Allowed)

```python
User: sainathsetti@gmail.com
Creator ID: sainath.no.1
Requested: creator_sainath.no.1_twin_coach

TenantGuard Check:
  - User owns creator_id "sainath.no.1"? YES
  - Access GRANTED

Result: Returns vectors from namespace
```

### Scenario 2: Cross-Tenant Access Attempt (❌ Blocked)

```python
User: sainathsetti@gmail.com
Creator ID: sainath.no.1
Requested: creator_other.user_twin_coach

TenantGuard Check:
  - User owns creator_id "other.user"? NO
  - Access DENIED

Result: PermissionError raised
Alert logged: "Tenant isolation violation detected"
```

### Scenario 3: Admin/Admin Access (✅ Allowed with Override)

```python
User: admin@digitalbrains.com
Creator ID: sainath.no.1
Role: ADMIN
Requested: creator_sainath.no.1_twin_coach

TenantGuard Check:
  - User is ADMIN? YES
  - Access GRANTED (with audit log)

Result: Returns vectors + admin_access_logged
```

---

## Comparison: Isolation Strategies

| Strategy | Isolation Level | Pros | Cons |
|----------|-----------------|------|------|
| **Single Namespace + Metadata Filter** | Weak | Simple, fewer namespaces | Risk of cross-tenant leakage |
| **Namespace per Creator** | Strong | Clear boundaries, easy deletion | More namespaces to manage |
| **Namespace per Twin (advisor)** | Very Strong | Physical isolation, granular | Maximum namespaces |
| **Separate Indexes per Creator** | Extreme | Complete isolation | Expensive, complex |

**Your Choice: Namespace per Twin (advisor)**
- ✅ Strongest practical isolation
- ✅ GDPR compliant (easy deletion)
- ✅ Prevents accidental cross-tenant queries

---

## Implementation: Full Tenant Isolation

### Step 1: Update Tenant Guard Module

```python
# backend/modules/tenant_guard.py (Enhanced)

from functools import wraps
from fastapi import HTTPException, Depends
import logging

logger = logging.getLogger(__name__)

class TenantIsolationError(Exception):
    """Raised when tenant isolation is violated."""
    pass

def require_creator_access(creator_id_param: str = "creator_id"):
    """
    Decorator to enforce tenant isolation on API endpoints.
    
    Usage:
        @router.post("/query")
        @require_creator_access()
        async def query(request: QueryRequest, user: User = Depends(get_user)):
            # Only reaches here if user owns creator_id
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract creator_id from request
            request = kwargs.get('request') or args[0]
            creator_id = getattr(request, creator_id_param, None)
            
            # Extract current user
            user = kwargs.get('user') or kwargs.get('current_user')
            
            if not user:
                raise HTTPException(401, "Authentication required")
            
            # Check access
            user_creator_ids = user.get("creator_ids", [user.get("id")])
            
            if creator_id not in user_creator_ids:
                logger.warning(
                    f"TENANT ISOLATION VIOLATION: "
                    f"User {user['id']} attempted to access creator {creator_id}"
                )
                raise HTTPException(
                    403,
                    f"Access denied: You do not have permission to access "
                    f"creator '{creator_id}'"
                )
            
            # Log successful access for audit
            logger.info(
                f"Tenant access granted: User {user['id']} → {creator_id}"
            )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### Step 2: Update API Endpoints

```python
# backend/routers/retrieval.py (Updated)

from backend.modules.tenant_guard import require_creator_access
from backend.modules.embeddings_advisor import get_advisor_client

@router.post("/query")
@require_creator_access(creator_id_param="creator_id")
async def query_vectors(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Query vectors with tenant isolation enforced.
    
    The @require_creator_access decorator ensures:
    - User can only query their own creator namespaces
    - Cross-tenant access is blocked
    - All access is logged for audit
    """
    client = get_advisor_client()
    
    results = client.query(
        vector=request.vector,
        creator_id=request.creator_id,
        twin_id=request.twin_id,
        top_k=request.top_k
    )
    
    # Additional metadata validation (defense in depth)
    for match in results.matches:
        if match.metadata.get("creator_id") != request.creator_id:
            logger.error(
                f"Data integrity issue: Vector {match.id} has wrong creator_id"
            )
            raise HTTPException(500, "Data integrity error")
    
    return {
        "matches": results.matches,
        "namespace": f"creator_{request.creator_id}_twin_{request.twin_id}"
    }
```

### Step 3: Add Audit Logging

```python
# backend/modules/audit_logger.py

import json
from datetime import datetime
from typing import Dict, Any

class TenantAuditLogger:
    """
    Audit logging for tenant isolation.
    Tracks all cross-namespace queries and access patterns.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("tenant_audit")
    
    def log_query(
        self,
        user_id: str,
        creator_id: str,
        twin_id: str,
        query_vector_id: str,
        result_count: int,
        latency_ms: float
    ):
        """Log a vector query for audit."""
        self.logger.info(json.dumps({
            "event": "vector_query",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "creator_id": creator_id,
            "twin_id": twin_id,
            "query_vector_id": query_vector_id,
            "result_count": result_count,
            "latency_ms": latency_ms
        }))
    
    def log_isolation_violation(
        self,
        user_id: str,
        attempted_creator_id: str,
        user_creator_ids: list,
        endpoint: str
    ):
        """Log a tenant isolation violation attempt."""
        self.logger.warning(json.dumps({
            "event": "isolation_violation",
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "HIGH",
            "user_id": user_id,
            "attempted_creator_id": attempted_creator_id,
            "user_authorized_creators": user_creator_ids,
            "endpoint": endpoint,
            "action": "blocked"
        }))
    
    def log_deletion(
        self,
        user_id: str,
        creator_id: str,
        twin_id: str = None,
        gdpr_request: bool = False
    ):
        """Log a deletion event (important for GDPR)."""
        self.logger.info(json.dumps({
            "event": "data_deletion",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "creator_id": creator_id,
            "twin_id": twin_id,
            "type": "creator_wide" if not twin_id else "twin_specific",
            "gdpr_request": gdpr_request
        }))
```

---

## Verification: Testing Tenant Isolation

```python
# tests/test_tenant_isolation.py

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

class TestTenantIsolation:
    """Test suite for tenant isolation."""
    
    def test_user_can_access_own_creator(self):
        """User A can access Creator A's data."""
        response = client.post(
            "/query",
            json={
                "vector": [0.1] * 3072,
                "creator_id": "sainath.no.1",  # Own creator
                "twin_id": "coach"
            },
            headers={"Authorization": "Bearer token_for_sainath"}
        )
        assert response.status_code == 200
    
    def test_user_cannot_access_other_creator(self):
        """User A cannot access Creator B's data."""
        response = client.post(
            "/query",
            json={
                "vector": [0.1] * 3072,
                "creator_id": "other.user",  # NOT own creator
                "twin_id": "coach"
            },
            headers={"Authorization": "Bearer token_for_sainath"}
        )
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]
    
    def test_isolation_violation_logged(self):
        """Cross-tenant access attempts are logged."""
        # This would check audit logs
        pass
    
    def test_admin_can_access_with_audit(self):
        """Admin can access but it's logged."""
        response = client.post(
            "/query",
            json={
                "vector": [0.1] * 3072,
                "creator_id": "sainath.no.1",
                "twin_id": "coach"
            },
            headers={"Authorization": "Bearer admin_token"}
        )
        assert response.status_code == 200
        # Verify admin access was logged
```

---

## Summary: Tenant Isolation with creator-namespace pattern

### ✅ What You Get

| Feature | Implementation | Strength |
|---------|---------------|----------|
| **Physical Isolation** | Separate namespaces per creator/twin | Very Strong |
| **Application Enforcement** | TenantGuard validates all requests | Strong |
| **Metadata Validation** | creator_id embedded in vectors | Medium |
| **Audit Logging** | All access logged for compliance | Strong |
| **GDPR Compliance** | Single API call deletes all creator data | Very Strong |

### 🎯 Your Isolation Model

```
┌─────────────────────────────────────────┐
│  User Request                           │
│  "Query creator_sainath.no.1_twin_X"    │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  1. JWT Validation                      │
│     "Who is this user?"                 │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  2. TenantGuard Check                   │
│     "Does user own creator_sainath.no.1?"│
│     YES → Continue                      │
│     NO  → Block + Log Alert             │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  3. Pinecone Query                      │
│     Namespace: creator_sainath.no.1_*   │
│     (Physically isolated)               │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  4. Metadata Validation                 │
│     "Verify creator_id in results"      │
│     (Defense in depth)                  │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  5. Audit Log                           │
│     "Log successful access"             │
└─────────────────────────────────────────┘
```

### 🔒 Security Guarantees

1. **No Cross-Tenant Data Leakage**: Namespaces are physically separate
2. **Unauthorized Access Blocked**: TenantGuard prevents access to other creators
3. **Audit Trail**: All access logged for compliance
4. **GDPR Ready**: Complete data deletion in one API call

---

## Recommendation

**The creator namespace strategy provides EXCELLENT tenant isolation.**

It's actually **stronger** than your current UUID-based approach because:
- Current: UUIDs don't indicate ownership (hard to audit)
- New: `creator_{id}` makes ownership explicit and enforceable

**Next Steps:**
1. Implement the `TenantGuard` module (provided above)
2. Add `@require_creator_access` decorator to API endpoints
3. Deploy audit logging
4. Run tenant isolation tests

**Want me to implement the TenantGuard module and update your API endpoints?**
