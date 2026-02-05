# Code Review Best Practices

> Comprehensive guide for conducting effective, efficient code reviews in the Verified Digital Twin Brain project

## 🎯 Quick Start

### For New Reviewers (5 minutes)

1. **Read** [CODE_REVIEW_GUIDELINES.md](./CODE_REVIEW_GUIDELINES.md)
2. **Check** the PR template is complete
3. **Verify** CI passes
4. **Scan** for critical issues (next section)
5. **Decide** approve/request changes/comment

### For Experienced Reviewers (2 minutes)

Use the review checklist at the bottom of this document.

---

## 🚨 Critical Issues Checklist (30 seconds)

Before diving deep, check these **automatic blockers**:

```
SECURITY & MULTI-TENANCY
☐ All DB queries have tenant_id filter (database queries only)
☐ All routes use Depends(get_current_user)
☐ All resource access has verify_owner() check
☐ No PII in logs or errors
☐ No hardcoded secrets in code

CODE QUALITY
☐ No obvious syntax errors
☐ No circular imports
☐ No N+1 queries
☐ Error handling present

DATABASE
☐ Schema changes have migrations
☐ Migrations include RLS policies
☐ Migration uses IF EXISTS/IF NOT EXISTS

ARCHITECTURE
☐ No modifications to _core/ unless extending
☐ No changes to auth_guard.py unless critical
☐ No changes to observability.py or clients.py
☐ Backward compatibility maintained
```

If ANY of these are violated → **REQUEST CHANGES**

---

## 🔍 Deep Review Protocol

### Phase 1: Context (5 min)
```
1. Read PR title and description
2. Check which files changed
3. Identify which area is affected (backend/frontend/database)
4. Check if CI is passing
5. Determine review depth needed
```

**Risk Assessment:**
- **Small + Green CI + Isolated Change** → Faster review (15 min)
- **Large + Multiple Areas + Critical Files** → Thorough review (60+ min)
- **Database + Breaking Change + No Tests** → Max scrutiny

### Phase 2: Functionality (10 min)

Ask yourself:
- Does this do what the PR claims?
- Are all happy paths covered?
- What about error cases?
- Are edge cases handled?

**Example Red Flags:**
```python
# ❌ Unhandled error case
result = external_api.fetch()  # What if this fails?
data = result['data']  # What if 'data' key missing?

# ✅ Proper error handling
try:
    result = external_api.fetch()
    if 'data' not in result:
        raise ValueError("Invalid API response")
    data = result['data']
except Exception as e:
    raise HTTPException(status_code=503, detail="External API error")
```

### Phase 3: Security (15 min) ⭐ CRITICAL

**Multi-Tenant Isolation**
```python
# ❌ WRONG - No tenant filter
twins = supabase.table("twins").select("*").execute()

# ✅ CORRECT - Filtered by tenant
twins = (supabase.table("twins")
    .select("*")
    .eq("tenant_id", user["tenant_id"])
    .execute())
```

**Authentication**
```python
# ❌ WRONG - No auth check
@router.get("/data")
async def get_data():
    return supabase.table("data").select("*").execute()

# ✅ CORRECT - Auth check
@router.get("/data")
async def get_data(user: dict = Depends(get_current_user)):
    verify_owner(user, resource_id)
    return supabase.table("data").select("*").eq("tenant_id", user["tenant_id"]).execute()
```

**PII & Secrets**
```python
# ❌ WRONG - Logging PII
logger.info(f"User {user['email']} logged in")  # Email is PII
logger.info(f"API Key: {api_key}")  # Secret in logs

# ✅ CORRECT - Hash or omit sensitive data
logger.info(f"User {hash(user['email'])} logged in")  # Or just "User logged in"
# Never log API keys
```

### Phase 4: Code Quality (10 min)

**Readability**
- Are function names clear?
- Is the code easy to follow?
- Are complex sections commented?

**DRY (Don't Repeat Yourself)**
```python
# ❌ WRONG - Repeated logic
if user.role == "admin":
    return {"access": "full"}
if user.role == "admin":
    return {"access": "full"}

# ✅ CORRECT - Single source of truth
def get_user_access(role: str):
    role_access = {"admin": "full", "user": "limited"}
    return {"access": role_access.get(role, "none")}
```

**Type Safety**
```python
# ❌ WRONG - No types (Python)
def process_data(data):
    return data.upper()

# ✅ CORRECT - Types specified
def process_data(data: str) -> str:
    return data.upper()
```

### Phase 5: Testing (5 min)

**Coverage Areas:**
- Happy path tested?
- Error cases tested?
- Edge cases tested?
- Integration tests if needed?

```python
# ✅ GOOD test structure
class TestChatEndpoint:
    async def test_chat_success(self):
        """Happy path: valid message returns response"""
        response = await chat(message="Hi")
        assert response.status_code == 200
    
    async def test_chat_unauthorized(self):
        """Error case: no auth token"""
        response = await chat(message="Hi", user=None)
        assert response.status_code == 401
    
    async def test_chat_empty_message(self):
        """Edge case: empty message"""
        response = await chat(message="")
        assert response.status_code == 400
```

### Phase 6: Documentation (5 min)

Check:
- Code comments present for complex logic?
- Docstrings for functions/classes?
- README updated if needed?
- PR description accurate?

---

## 📋 Review Checklist by Language

### Python/FastAPI

```
[ ] All imports at top of file
[ ] No circular imports
[ ] Functions have docstrings
[ ] Type hints present (Python 3.10+)
[ ] Exception handling with try/except
[ ] Async/await properly used
[ ] SQL queries use parameterized statements
[ ] No f-strings in SQL (use .eq() or parameters)
[ ] Dependency injection used (Depends)
[ ] Error responses have descriptive detail
[ ] Logging doesn't include PII
```

### TypeScript/React

```
[ ] All React hooks imported
[ ] No missing dependencies in useEffect/useCallback
[ ] Components properly typed
[ ] Props interface defined
[ ] Error boundaries present
[ ] Accessibility (a11y) considered
[ ] No console.log in production code
[ ] State management clear
[ ] Side effects in useEffect
[ ] Async operations properly handled
```

### SQL/Database

```
[ ] IF NOT EXISTS for idempotency
[ ] RLS policies included
[ ] Indexes on foreign keys
[ ] No N+1 query patterns
[ ] Soft deletes where appropriate
[ ] Audit trail for sensitive data
[ ] Migration is reversible
[ ] Comments for complex logic
```

---

## 💬 Review Comment Quality

### ✅ GOOD Comments

```markdown
**Why**: Explains the reason, not just "fix this"
**Context**: Links to docs/code/standards
**Solution**: Provides example or clear direction

---

🔒 **Security**: Multi-tenant isolation

This query is missing the tenant filter. Without it, users could access other users' data.

Change from:
```python
result = supabase.table("twins").select("*").eq("twin_id", id).execute()
```

To:
```python
result = (supabase.table("twins")
    .select("*")
    .eq("twin_id", id)
    .eq("tenant_id", user["tenant_id"])
    .execute())
```

Reference: `docs/ai/agent-manual.md` → Multi-Tenant Filters section
```

### ❌ POOR Comments

```
Bad: "This is wrong"
Bad: "Fix this"
Bad: "Why did you do this?"
Bad: Generic: "Add error handling"
```

---

## ⏱️ Review Speed Guidelines

| Change Type | Typical Time | Max Time |
|---|---|---|
| Bug fix (small) | 10-15 min | 20 min |
| Feature (small) | 20-30 min | 45 min |
| Feature (medium) | 30-60 min | 90 min |
| Refactor | 20-40 min | 60 min |
| Database migration | 15-30 min | 45 min |
| Critical file change | 30-60 min | 120 min |

If review is taking longer than max time:
- Split analysis into multiple sessions
- Flag architectural questions for lead review
- Ask author for clarification
- Request smaller PR if possible

---

## 🎯 Smart Review Tactics

### 1. Follow the Architecture

For core changes, check:
- `docs/architecture/system-overview.md` - System design
- `docs/ai/agent-manual.md` - Project conventions
- `.cursorrules` - Coding standards
- `CRITICAL_PATH_*` files - Critical flows

### 2. Use Git Blame

```bash
git blame <file> <line>  # See why this code exists
git log -p <file>       # See change history
```

This helps understand context and precedent.

### 3. Check the Diff

GitHub shows:
- Red lines = removed
- Green lines = added
- Look at context lines for what was there before

### 4. Test Locally (If Complex)

For database changes or complex logic:
```bash
git fetch origin <branch>
git checkout <branch>
npm run lint && npm run test  # Frontend
pytest -v                      # Backend
```

### 5. Ask Clarifying Questions

Don't assume. Ask:
- "Why choose this approach over...?"
- "How does this affect...?"
- "What about this edge case...?"

Good questions help author and other reviewers.

---

## 🚫 Anti-Patterns to Watch For

### Code Smells

| Pattern | Issue | Fix |
|---------|-------|-----|
| Function > 50 lines | Too complex | Extract functions |
| If/else nesting > 3 levels | Hard to follow | Use guards/early return |
| Class > 300 lines | Too many responsibilities | Extract classes |
| Module imports everything | High coupling | Limit imports |
| No error handling | Silent failures | Add try/catch |

### Architecture Violations

| Pattern | Issue | Fix |
|---------|-------|-----|
| Creating duplicate clients | Resource leak | Use `modules/clients.py` |
| Skipping auth checks | Security risk | Add `Depends(get_current_user)` |
| Missing tenant filters | Data leak | Add `.eq("tenant_id", ...)` |
| Modifying `_core/` modules | Cascade failures | Use composition |
| Hardcoded secrets | Security risk | Use `.env` variables |

---

## ✅ Final Approval Checklist

Before you click "Approve":

```
SECURITY (CRITICAL)
☐ All queries filtered by tenant_id (database only)
☐ All routes authenticated with Depends(get_current_user)
☐ All resource access verified with verify_owner()
☐ No secrets in code
☐ No PII in logs

FUNCTIONALITY
☐ PR description accurate
☐ Implementation matches design
☐ Edge cases handled
☐ Error messages helpful

CODE QUALITY
☐ Follows project conventions
☐ No obvious bugs
☐ Tests added for new code
☐ Code is readable

TESTING
☐ CI passing
☐ Tests cover happy path + errors
☐ Manual testing (if needed) done

DATABASE
☐ Schema changes have migrations
☐ RLS policies included
☐ Migration tested in Supabase

DOCUMENTATION
☐ Code comments present
☐ README updated (if needed)
☐ API contracts documented
☐ Complex logic explained
```

---

## 🔄 Handling Author Responses

### If Author Disputes Your Concern

1. **Discuss respectfully** - Maybe you missed context
2. **Reference standards** - Link to docs/guidelines
3. **Suggest compromise** - Sometimes both approaches work
4. **Escalate if needed** - Get second opinion from lead architect

### If Author Agrees But Needs Time

1. **Allow follow-up commit** - Don't block on small fixes
2. **Check it in follow-up** - Verify fix is correct
3. **Re-approve once done** - Don't make author wait

---

## 📊 Reviewer Metrics

Track these to improve:
- Average review time per PR
- Time to first review (turnaround)
- Issues caught in review vs. production
- Reviewer agreement rate (consistency)

---

## 🎓 Learn from Reviews

Each review is a learning opportunity:

**For Reviewers:**
- See new patterns
- Learn from mistakes
- Improve project knowledge

**For Authors:**
- Get feedback earlier
- Learn standards
- Improve coding skills

---

## 🚀 Advanced: Automating Reviews

### Use GitHub Actions

Automated checks for:
- Security scanning
- Dependency vulnerabilities
- Code coverage
- Lint/type errors
- Architecture violations

See: `.github/workflows/code-review.yml`

### Use Code Review Tools

- **SonarQube** - Quality metrics
- **CodeClimate** - Code health
- **Dependabot** - Dependency updates
- **LGTM** - Security scanning

---

## 📞 Getting Help

**Questions about standards?**
→ Read `.cursorrules` and `docs/ai/agent-manual.md`

**Security concerns?**
→ Check `docs/KNOWN_FAILURES.md` and security section above

**Architecture questions?**
→ See `docs/architecture/system-overview.md`

**Code review help?**
→ Ask in #code-review Slack channel or open discussion

---

## Summary: The 80/20 Rule

Focus your review effort here for maximum impact:

1. **20% Security** → 80% of critical issues
   - Tenant isolation
   - Authentication
   - Authorization
   - PII/Secrets

2. **10% Architecture** → 40% of long-term problems
   - Critical file changes
   - API contracts
   - Database schema

3. **10% Testing** → 30% of bugs escaping to production
   - Happy path coverage
   - Error cases
   - Edge cases

4. **60% Other** (style, naming, etc.)
   - Still important
   - Lower impact on project health

---

**Remember**: Code review is collaborative, not confrontational. The goal is to build better software together, faster.
