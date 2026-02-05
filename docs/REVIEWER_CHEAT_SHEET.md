---
name: Code Review Quick Checklist
---

# 🎯 Code Review Quick Checklist
**Print This! Keep It Handy!**

---

## ⚡ 30-SECOND SECURITY AUDIT

Before you do anything else, check:

```
☐ SELECT * without tenant_id → STOP, REQUEST CHANGES
☐ Route without Depends(get_current_user) → STOP, REQUEST CHANGES  
☐ Resource access without verify_owner() → STOP, REQUEST CHANGES
☐ Hardcoded secrets or API keys → STOP, REQUEST CHANGES
☐ PII in logs or error messages → STOP, REQUEST CHANGES
☐ SQL string concatenation (injection risk) → STOP, REQUEST CHANGES
```

---

## ✅ QUICK SCAN (1-2 minutes)

```
[ ] PR template complete?
[ ] CI tests passing?
[ ] Size reasonable (< 500 LOC)?
[ ] Scope matches description?
```

---

## 🔍 CODE REVIEW (10-50 minutes, depending on size)

### SECURITY (50% of your time)
```
[ ] All DB queries filter by tenant_id
[ ] All routes authenticated (Depends(get_current_user))
[ ] All resources verified (verify_owner())
[ ] No secrets in code
[ ] No PII in logs
```

### FUNCTIONALITY (30% of your time)
```
[ ] Does what PR claims
[ ] Error cases handled
[ ] Edge cases considered
[ ] Tests added for new code
```

### CODE QUALITY (20% of your time)
```
[ ] Readable code
[ ] Follows .cursorrules
[ ] No obvious bugs
[ ] Follows project conventions
```

---

## 💬 DECISION

### APPROVE ✅
- No issues found
- Click: Approve

### REQUEST CHANGES 🔴
- Security issue
- Logic error
- No tests
- Click: Request Changes + Comment

### COMMENT 💬
- Just suggestions
- Click: Comment (don't block)

---

## 📝 QUICK COMMENT TEMPLATES

### Security Issue
```
🔒 **Security**: Multi-tenant isolation

This query needs a tenant filter:
.eq("tenant_id", user["tenant_id"])

Reference: agent-manual.md → Multi-Tenant Filters
```

### Missing Tests
```
⚡ **Testing**: Missing test coverage

Add test for [area]:
@pytest.mark.asyncio
async def test_[scenario]():
    # Test implementation
```

### Code Smell
```
♻️ **Refactor**: DRY violation

This logic repeats 3x. Extract to:
def shared_logic():
    # Shared implementation
```

### Suggestion (Non-blocking)
```
💡 **Suggestion**: Consider [approach]

Instead of: [current code]
Try: [suggested code]

(Not blocking, just an idea!)
```

---

## ⏱️ REVIEW TIME ESTIMATES

| PR Size | Time |
|---------|------|
| Tiny (1-3 files) | 10-15 min |
| Small (3-5 files) | 15-30 min |
| Medium (5-10 files) | 30-60 min |
| Large (10+ files) | 60+ min |

**Rule**: If taking longer than estimate, consider splitting review

---

## 🚨 AUTOMATIC BLOCKERS

**THESE MUST BE FIXED:**

- No multi-tenant filter on DB queries
- No auth check on protected routes
- Hardcoded secrets
- No tests for new code
- Missing migration for schema change
- Circular imports
- Breaking API change without documentation

---

## 🔧 LANGUAGE CHECKLISTS

### Python
```
[ ] Type hints present
[ ] Imports organized
[ ] Error handling with try/except
[ ] No f-strings in SQL
[ ] Async/await patterns correct
[ ] Dependency injection used
```

### TypeScript/React
```
[ ] React hooks imported
[ ] useEffect dependencies correct
[ ] Props typed
[ ] No console.log in production
[ ] Error boundaries present
```

### SQL
```
[ ] IF NOT EXISTS for idempotency
[ ] RLS policies included
[ ] Indexes on foreign keys
[ ] Reversible migration
```

---

## 📊 QUICK CHECKLIST BY FILE TYPE

### If changed: `backend/modules/_core/`
```
☐ Notify lead architect
☐ Very thorough review
☐ Check if extending vs. modifying
☐ Ask: Does this break specializations?
```

### If changed: `backend/main.py`
```
☐ Notify lead architect
☐ Check: Middleware order preserved?
☐ Check: CORS config correct?
☐ Check: Auth middleware untouched?
```

### If changed: Database files
```
☐ Migration included?
☐ RLS policies added?
☐ IF NOT EXISTS present?
☐ Reversible?
☐ Tested in Supabase?
```

### If changed: Auth/security
```
☐ Notify lead architect
☐ Very thorough review
☐ Check: Pattern followed?
☐ Check: No shortcuts?
```

---

## 🚦 DECISION QUICK REFERENCE

| Finding | Decision | Why |
|---------|----------|-----|
| Security issue | REQUEST CHANGES | Blocking |
| Missing tests | REQUEST CHANGES | Quality |
| Logic error | REQUEST CHANGES | Functional |
| Style suggestion | COMMENT | Non-blocking |
| Good + minor suggestions | APPROVE | Minor improvements |
| Perfect code | APPROVE | Ready to merge |

---

## 🎯 TOP 5 THINGS TO CHECK

1. **Multi-tenant isolation** - Every query filtered?
2. **Authentication** - Every route authenticated?
3. **Tests** - New code tested?
4. **Error handling** - What if things fail?
5. **Breaking changes** - Backward compatible?

---

## 📞 WHEN TO ASK FOR HELP

```
Uncertain about security → Escalate to @lead-architect
Don't understand requirement → Ask author in comment
Huge PR size → Suggest splitting into multiple PRs
Code quality question → Reference .cursorrules
Architecture question → Reference docs/architecture/
```

---

## ✨ TIPS FOR FAST REVIEWS

1. **Use templates** - Copy/paste comments
2. **Reference docs** - Don't retype explanations
3. **Focus on security** - Catch the big issues
4. **Ask questions** - Clarify intent
5. **Batch feedback** - Group related comments

---

## 🎓 REMEMBER

- 🔒 **Security First** - Most important
- 👥 **Be Respectful** - Collaborative tone
- 🔗 **Link Context** - Help author learn
- 🚀 **Unblock Others** - Don't over-nitpick
- 📚 **Reference Docs** - Use standards

---

## 📍 WHERE TO FIND THINGS

| Need | Find In |
|------|---------|
| Details | docs/CODE_REVIEW_GUIDELINES.md |
| Quick answers | docs/CODE_REVIEW_QUICK_REFERENCE.md |
| New reviewer? | docs/REVIEWER_ONBOARDING.md |
| Code standards | .cursorrules |
| Project patterns | docs/ai/agent-manual.md |
| Architecture | docs/architecture/system-overview.md |

---

**Print this. Keep it at your desk. Reference it every review! ✅**
