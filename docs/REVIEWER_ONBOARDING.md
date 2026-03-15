# Reviewer Onboarding Guide

> Welcome to the Verified Digital Twin Brain code review team! 🎉
> This guide will get you productive as a reviewer in 30 minutes.

---

## 📚 Step 1: Read Essential Documents (10 min)

Before reviewing your first PR, read:

### Quick Setup (5 min)
1. [CODE_REVIEW_QUICK_REFERENCE.md](./CODE_REVIEW_QUICK_REFERENCE.md) - **Start here!**
   - 30-second security audit
   - Quick checklists
   - Comment templates

2. [CODE_REVIEW_GUIDELINES.md](./CODE_REVIEW_GUIDELINES.md) - **Core Reference**
   - What to look for
   - Critical flags
   - PR size guidelines

### Deep Knowledge (5 min)
3. [CODE_REVIEW_BEST_PRACTICES.md](./CODE_REVIEW_BEST_PRACTICES.md) - **Advanced**
   - Deep review protocol
   - Language-specific checks
   - Anti-patterns to watch

---

## 🔐 Step 2: Understand Multi-Tenant Security (5 min)

This is THE critical concept:

### The Golden Rule
> **Every database query MUST filter by `tenant_id` or `twin_id`**

```python
# ❌ WRONG - Potential data leak!
users = supabase.table("users").select("*").execute()

# ✅ CORRECT - Scoped to current tenant
users = (supabase.table("users")
    .select("*")
    .eq("tenant_id", user["tenant_id"])
    .execute())
```

**Why?** Without tenant filtering, one user could access another user's data.

### The Second Golden Rule
> **Every route MUST verify the user's authentication and ownership**

```python
# ❌ WRONG - No auth check!
@router.get("/twins/{twin_id}")
async def get_twin(twin_id: str):
    return twin_data

# ✅ CORRECT - Auth + ownership check
@router.get("/twins/{twin_id}")
async def get_twin(
    twin_id: str,
    user: dict = Depends(get_current_user)  # Auth check
):
    verify_owner(user, twin_id)  # Ownership check
    return twin_data
```

**Why?** Ensures users can only access their own resources.

---

## 🎯 Step 3: Know the Critical Files (3 min)

These files are **foundation** - changes here affect everything:

| File | Role | Review Strictness |
|------|------|---|
| `backend/modules/_core/` | Core orchestration | 🔴 Very strict |
| `backend/modules/auth_guard.py` | Auth patterns | 🔴 Very strict |
| `backend/modules/observability.py` | DB singleton | 🔴 Very strict |
| `backend/modules/clients.py` | API clients | 🔴 Very strict |
| `backend/main.py` | CORS & middleware | 🟠 Strict |
| `frontend/proxy.ts` | Auth redirects | 🟠 Strict |

**Rule**: If a PR changes these, notify lead architect immediately.

---

## ✅ Step 4: Your First Review - Checklist

### Before You Start
```
[ ] I've read CODE_REVIEW_QUICK_REFERENCE.md
[ ] I understand multi-tenant filtering requirement
[ ] I know the critical files that need strict review
```

### During Review

**30 seconds:**
- [ ] PR template complete?
- [ ] CI passing?
- [ ] Size reasonable?

**5 minutes:**
- [ ] Does it do what PR claims?
- [ ] Any obvious bugs?
- [ ] Correct approach used?

**5 minutes - SECURITY FOCUS:**
- [ ] All queries filter by tenant_id?
- [ ] All routes have auth check?
- [ ] No hardcoded secrets?

**5 minutes:**
- [ ] Code quality good?
- [ ] Tests added?
- [ ] Documentation updated?

**1 minute:**
- Decide: Approve / Request Changes / Comment

---

## 🚦 Step 5: Decision Matrix

### APPROVE ✅
```
When:
- No issues found
- Code quality good
- Tests present
- Security OK
```

### REQUEST CHANGES 🔴
```
When:
- Security issue found
- Multi-tenant violation
- Logic error
- No tests for new code
- Breaking API change not documented
```

### COMMENT 💬
```
When:
- Just suggestions
- Doesn't block merge
- Educational feedback
```

---

## 💬 Step 6: Writing Good Comments

### Bad Comment ❌
```
"This is wrong"
"Fix this"
"Why did you do this?"
```

### Good Comment ✅
```
🔒 **Security Issue**: Multi-tenant isolation

This query doesn't filter by tenant_id:
```python
result = supabase.table("twins").select("*").execute()
```

Should include:
```python
.eq("tenant_id", user["tenant_id"])
```

See: `docs/ai/agent-manual.md` → Multi-Tenant Filters
```

---

## 📊 Step 7: Common Review Scenarios

### Scenario 1: PR Has No Tests
```
Problem: New code without test coverage
Action: REQUEST CHANGES
Comment: "New code needs tests. Add tests for [area]"
Reference: backend/tests/
```

### Scenario 2: PR Modifies Auth Code
```
Problem: Changes to authentication
Action: REQUEST CHANGES (unless trivial)
Comment: Notify lead architect
Reference: docs/ai/agent-manual.md → Auth Patterns
```

### Scenario 3: PR Missing Tenant Filter
```
Problem: Database query without tenant_id
Action: REQUEST CHANGES
Comment: "Add .eq('tenant_id', user['tenant_id'])"
Reference: docs/ai/agent-manual.md → Multi-Tenant Filters
```

### Scenario 4: Good Code with Minor Suggestions
```
Problem: Works fine, just style/naming suggestions
Action: APPROVE with comments
Comment: "💡 Could rename X to Y for clarity (not blocking)"
```

---

## 🔍 Step 8: Debugging Tips

### PR Seems Wrong But You're Not Sure
1. **Check related code**: Look at similar endpoints/functions
2. **Check git history**: `git log -p <file>` to see why it's written this way
3. **Check tests**: See what the tests expect
4. **Ask author**: "Help me understand..." (not accusatory)

### Unclear Security Implication
1. **Check `.cursorrules`** for patterns
2. **Check `agent-manual.md`** for security guidelines
3. **Ask lead architect** if still unsure

### Performance Concern?
1. **Check for N+1 queries**: Multiple queries in loop?
2. **Check for large data loads**: Loading all data then filtering?
3. **Check caching**: Is this query repeated unnecessarily?

---

## 📞 Step 9: Getting Help

### During Review
```
"I'm not sure about X"
→ Check docs first: CODE_REVIEW_QUICK_REFERENCE.md
→ Still unclear? Ask in #code-review channel
```

### Found Security Issue
```
→ FLAG IMMEDIATELY
→ REQUEST CHANGES
→ Notify lead architect if critical
```

### Need Architectural Context
```
→ See: docs/architecture/system-overview.md
→ See: docs/ai/agent-manual.md
```

### Stuck on a Decision
```
→ Ask in #code-review or escalate to team lead
```

---

## ✨ Step 10: Best Practices

### 1. Be Respectful
- Code review is collaboration, not criticism
- Assume positive intent
- Use constructive language

### 2. Be Clear
- Explain WHY, not just WHAT
- Link to documentation
- Provide examples

### 3. Be Efficient
- Focus on high-impact issues (security, logic)
- Don't nitpick formatting (that's what linters do)
- Use templates to save time

### 4. Be Consistent
- Apply same standards to all reviewers
- Reference same documentation
- Use same comment style

### 5. Be Thorough
- Check security even on "small" PRs
- Verify tests aren't skipped
- Don't approve if uncertain

---

## 📋 Your Review Checklist

**Before approving ANY PR, verify:**

```
SECURITY (Most Critical)
☐ All database queries filter by tenant_id
☐ All routes use Depends(get_current_user)
☐ All resource access checks verify ownership
☐ No secrets in code
☐ No PII in logs

FUNCTIONALITY
☐ PR does what it claims
☐ Error cases handled
☐ Edge cases considered

CODE QUALITY
☐ Readable and follows conventions
☐ No obvious bugs
☐ Tests added

TESTING
☐ CI passing
☐ New code tested
☐ Existing tests not broken

DATABASE (if applicable)
☐ Migration included
☐ RLS policies added
```

---

## 🎓 Learning Path

### Week 1: Get Started
- [ ] Read Step 1-3 above
- [ ] Do your first review (easy PR)
- [ ] Ask questions in #code-review

### Week 2: Build Skills
- [ ] Review 3-5 more PRs
- [ ] Reference docs as needed
- [ ] Notice patterns

### Week 3: Advanced Topics
- [ ] Review complex PRs
- [ ] Review database migrations
- [ ] Review critical file changes

### Week 4+: Master Level
- [ ] Lead review on complex PRs
- [ ] Help other reviewers
- [ ] Contribute to review standards

---

## 🚀 Quick Start: Your First PR Review

### Found a PR to review?

1. **Open quick reference** (30 sec)
   → [CODE_REVIEW_QUICK_REFERENCE.md](./CODE_REVIEW_QUICK_REFERENCE.md)

2. **Do 30-second security audit** (1 min)
   → Check: tenant filters, auth checks, no secrets

3. **Review PR description** (2 min)
   → Is it complete? Does it make sense?

4. **Check CI status** (1 min)
   → Are all tests passing?

5. **Scan code changes** (5-10 min)
   → Use quick reference checklist

6. **Write comments** (5 min)
   → Use templates from reference

7. **Make decision** (1 min)
   → Approve / Request Changes / Comment

**Total: 15-20 minutes for typical PR**

---

## 📞 Support Resources

| Need | Resource |
|------|----------|
| Quick answers | `docs/CODE_REVIEW_QUICK_REFERENCE.md` |
| Detailed guide | `docs/CODE_REVIEW_GUIDELINES.md` |
| Security patterns | `docs/ai/agent-manual.md` |
| Code standards | `.cursorrules` |
| Architecture | `docs/architecture/system-overview.md` |
| Chat help | #code-review Slack channel |

---

## ✅ Onboarding Complete!

You're now ready to review PRs. Remember:

1. **Security first** - Catch multi-tenant violations
2. **Be constructive** - Help the team improve
3. **Reference docs** - Never guess on standards
4. **Ask for help** - It's OK to be uncertain
5. **Stay consistent** - Use same criteria for all PRs

**Go review your first PR! 🚀**

---

**Questions or feedback?** Post in #code-review or reach out to your team lead.
