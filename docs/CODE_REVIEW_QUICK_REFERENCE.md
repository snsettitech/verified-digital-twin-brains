# Code Review Quick Reference

> Fast lookup guide for code reviewers - Print this or keep it handy

## ⚡ 30-Second Security Audit

**STOP and REQUEST CHANGES if you see:**

```
❌ SELECT * without tenant_id filter
❌ Route without Depends(get_current_user)
❌ Resource access without verify_owner()
❌ Hardcoded API keys, passwords, or secrets
❌ PII in logs or error messages
❌ SQL string concatenation (injection risk)
```

## 🔍 Quick Scan Checklist

**Before diving into code review:**

```
[ ] PR template is complete
    → Missing section = REQUEST CHANGES
[ ] CI tests are passing
    → Failing CI = likely blocker
[ ] No huge file changes (>500 LOC)
    → Too large = ask for split
[ ] Change scope matches description
    → Scope creep = ask for clarification
[ ] Reviewer assigned is appropriate
    → Wrong reviewer = reassign
```

## 📊 Review Time Estimate

| Scenario | Time |
|----------|------|
| Small bug fix (1-2 files) | 10-15 min |
| Small feature (3-5 files) | 20-30 min |
| Medium feature (5-10 files) | 30-60 min |
| Large feature (10+ files) | 60+ min |
| Database migration | 15-30 min |
| Refactor | 20-40 min |
| Critical file change | 30-60 min |

**Rule**: If taking longer than expected, consider splitting into phases

## 🎯 Focus Areas by Language

### Python (Backend)
```
✓ Type hints present (Python 3.10+)
✓ Imports organized (stdlib, 3rd party, local)
✓ Error handling with try/except
✓ No f-strings in SQL (use parameterized)
✓ Async/await patterns correct
✓ Dependency injection used
```

### TypeScript/React (Frontend)
```
✓ All React hooks imported
✓ useEffect dependencies correct
✓ Props fully typed
✓ No console.log in production
✓ Error boundaries present
✓ Accessibility (a11y) considered
```

### SQL (Database)
```
✓ IF NOT EXISTS for idempotency
✓ RLS policies included
✓ Indexes on foreign keys
✓ Reversible migrations
✓ Comments for complex logic
```

## 🚨 Automatic Blockers

**These MUST be fixed before approval:**

| Category | Blocker |
|----------|---------|
| Security | Missing auth check, no tenant filter, hardcoded secrets |
| Logic | Obvious bug, unhandled error, infinite loop |
| Testing | No test added for new code |
| Architecture | Changes to `_core/` or `auth_guard.py`, circular imports |
| Database | Migration without RLS, schema mismatch |

## 💬 Comment Template Library

### Security Issue
```
🔒 **Security**: Multi-tenant isolation

This query is missing tenant_id filter. Add:
.eq("tenant_id", user["tenant_id"])

Reference: agent-manual.md → Multi-Tenant Filters
```

### Testing Gap
```
⚡ **Test Coverage**: Missing error case

Add test for when external API fails:
@pytest.mark.asyncio
async def test_api_error():
    # Test implementation
```

### Code Smell
```
♻️ **Refactor**: DRY violation

This logic is repeated 3 times. Extract to function:
def calculate_discount(amount):
    # Shared logic
```

### Suggestion
```
💡 **Suggestion**: Consider using...

Instead of manual error handling, use:
from contextlib import contextmanager

# Usage example
```

## ✅ Approval Checklist (TL;DR)

```
SECURITY          | ✓ Tenant filters, auth checks, no secrets
FUNCTIONALITY     | ✓ Does what PR claims, handles errors
TESTING          | ✓ Tests added for new code
CODE QUALITY     | ✓ Readable, follows conventions
DATABASE (if applicable) | ✓ Migration included, RLS policies
```

## 🔄 Common Review Patterns

### Pattern: Incomplete PR Description
```
Response: REQUEST CHANGES
Message: PR template incomplete. Add [missing section]
Link: .github/PULL_REQUEST_TEMPLATE.md
```

### Pattern: Missing Tests
```
Response: REQUEST CHANGES
Message: New code needs tests. Add tests for [logic area]
Link: backend/tests/ (example structure)
```

### Pattern: Security Issue
```
Response: REQUEST CHANGES
Message: Multi-tenant isolation issue. All queries must filter by tenant_id
Link: docs/ai/agent-manual.md → Multi-Tenant Filters
```

### Pattern: Stylistic Nitpick
```
Response: COMMENT (don't block)
Message: 💡 Minor suggestion: Could rename X to Y for clarity
```

### Pattern: Architectural Question
```
Response: COMMENT
Message: ❓ How does this integrate with [system]? 
         See docs/architecture/system-overview.md for context
```

## 📞 Escalation Matrix

**When to involve others:**

| Situation | Action | Who |
|-----------|--------|-----|
| Security concern | Flag immediately | Lead Architect, Security Team |
| Unclear requirement | Ask author | PR Author |
| Architecture impact | Second review | Lead Architect |
| Performance regression | Investigate | DevOps, Backend Lead |
| Merge conflict | Resolve first | PR Author |
| Code style question | Reference standards | Reference `.cursorrules` |

## 📈 Reviewer Self-Check

**Track these metrics:**

```
✓ Average review time: _____ min
✓ Issues missed (found in production): _____
✓ Back-and-forth iterations per PR: _____
✓ Approval rate (approved vs requested changes): _____%
```

**Goal**: Fast, thorough, constructive reviews

## 🎓 Advanced Tips

### Tip 1: Read Related Code
Understanding context makes reviews faster and better:
```bash
git log -p <file>  # See change history
git blame <file>   # See why code exists
```

### Tip 2: Check for Side Effects
Ask: What else could break?
- Database changes → Check queries
- API changes → Check frontend
- Auth changes → Check all routes

### Tip 3: Verify with Tools
```bash
# In terminal
git diff origin/main...HEAD  # See all changes
git show --stat              # Summary of changes
```

### Tip 4: Use Git Comments
Reply directly to code lines for precise feedback:
```
Line 42: Consider error handling here
```

### Tip 5: Suggest Improvements
Rather than just finding issues:
```
❌ WRONG: "This is bad"
✅ RIGHT: "Consider X, because Y. Here's how: [example]"
```

## 📚 Reference Documents

Quick links for common questions:

| Question | Reference |
|----------|-----------|
| How do I handle auth? | `docs/ai/agent-manual.md` → Auth Patterns |
| Multi-tenant isolation? | `docs/ai/agent-manual.md` → Multi-Tenant Filters |
| Database standards? | `docs/ai/agent-manual.md` → Database Migrations |
| Code conventions? | `.cursorrules` |
| Architecture? | `docs/architecture/system-overview.md` |
| Known issues? | `docs/KNOWN_FAILURES.md` |
| This guide? | `docs/CODE_REVIEW_QUICK_REFERENCE.md` |

## 🎯 Remember

1. **Security First** - Catch security issues every time
2. **Be Respectful** - Code review is collaboration, not criticism
3. **Provide Context** - Why > What. Explain reasoning
4. **Ask Questions** - Don't assume, clarify with author
5. **Celebrate Wins** - Acknowledge good code and improvements
6. **Learn Together** - Every review is a teaching moment

---

**Quick Actions:**
- 👍 **Approve** if ready (no issues)
- 💬 **Comment** if just suggestions (don't block)
- ❌ **Request Changes** if must fix (blocking)

---

**Time-pressed? Use this priority:**
1. Security (spend 50% of time)
2. Functionality (spend 30% of time)
3. Code Quality (spend 20% of time)
