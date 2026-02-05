# Code Review Guidelines

> Last Updated: February 2026  
> Purpose: Establish consistent, high-quality code review standards for the Verified Digital Twin Brain project

## 🎯 Core Principles

1. **Security First**: All reviews prioritize security and multi-tenant isolation
2. **Maintainability**: Code must be understandable and maintainable by the team
3. **Standards Adherence**: Follow project conventions and best practices
4. **Learning Culture**: Use reviews as teaching opportunities, not gatekeeping
5. **Efficiency**: Balance thoroughness with velocity

## 📋 Reviewer Responsibilities

### Before Starting Review
- [ ] Check if PR is in `draft` status (skip full review if so)
- [ ] Verify PR template is properly completed
- [ ] Identify the PR scope (small/medium/large/architectural)
- [ ] Check if migrations are involved (requires extra scrutiny)
- [ ] Look for changes to critical files (flag for lead architect review)

### During Review

#### Functionality & Logic
- [ ] Does the code do what the PR description claims?
- [ ] Are there any obvious logic errors or edge cases missed?
- [ ] Are error conditions properly handled?
- [ ] Do test cases cover the main scenarios?

#### Security & Multi-Tenancy
- [ ] **CRITICAL**: Are all database queries filtered by `tenant_id` or `twin_id`?
- [ ] Are JWT tokens properly validated with `Depends(get_current_user)`?
- [ ] Is ownership verified with `verify_owner()` before resource access?
- [ ] Are there any new endpoints accessible without auth?
- [ ] Is PII (personally identifiable information) being logged or exposed?
- [ ] Are external API calls properly scoped to the current user/tenant?

#### Code Quality
- [ ] Does code follow project conventions (`.cursorrules`, `AGENTS.md`)?
- [ ] Are function/variable names clear and descriptive?
- [ ] Is code DRY (Don't Repeat Yourself)?
- [ ] Are there any anti-patterns or code smells?
- [ ] Is error handling consistent and helpful?

#### Documentation & Tests
- [ ] Are complex functions/methods documented?
- [ ] Is new functionality tested?
- [ ] Are tests clear and maintainable?
- [ ] Is the PR description accurate and complete?

#### Architecture Impact
- [ ] **CRITICAL FILES**: Are changes to `_core/`, `auth_guard.py`, `observability.py`, `clients.py` minimal and necessary?
- [ ] Do changes maintain backward compatibility?
- [ ] Are there any database schema changes without migrations?
- [ ] Do changes affect the RAG retrieval path?
- [ ] Is the multi-tenant architecture compromised?

#### Performance
- [ ] Are there any obvious N+1 queries?
- [ ] Is new code doing unnecessary work in loops?
- [ ] Are rate limits respected?
- [ ] Is database connection pooling used?

#### Dependencies
- [ ] Are new dependencies necessary?
- [ ] Are version pins reasonable?
- [ ] Are there any security vulnerabilities in dependencies?

### After Review

#### Approval
```
✅ APPROVE with comments
- Use if no major issues, just suggestions for improvement
- Doesn't block merge, but improvements recommended

✅ APPROVE
- Use if code is ready to merge as-is
- No requested changes needed
```

#### Request Changes
```
🔴 REQUEST CHANGES (Blocking)
- Security issues
- Multi-tenant isolation violations
- Critical logic errors
- Missing test coverage for critical paths
- Unresolved conflicts with project standards
```

#### Comment
```
💬 COMMENT
- Use for optional suggestions
- Not blocking, just nice-to-haves
- Educational points
```

## 🚨 Critical Review Flags

### Automatic "REQUEST CHANGES"

| Flag | Reason | How to Resolve |
|------|--------|---|
| No `tenant_id` filter | Data leak risk | Add filter to all DB queries |
| No auth check | Unauthorized access | Add `Depends(get_current_user)` |
| Missing ownership verification | Cross-tenant access | Add `verify_owner()` call |
| PII in logs | Privacy violation | Remove or hash sensitive data |
| Hardcoded secrets | Security risk | Move to environment variables |
| Breaking API change | Incompatibility | Maintain backward compatibility or document clearly |
| Modifying `_core/` modules | Cascade failure risk | Use composition instead |
| No database migration | Schema mismatch | Create migration in `backend/database/migrations/` |
| Circular imports | Runtime errors | Refactor module structure |
| No error handling | Silent failures | Add try-catch and proper error responses |

## 📊 PR Size Guidelines

| Size | Files | Complexity | Review Time | Action |
|------|-------|-----------|---|---|
| **Tiny** | 1-3 | < 100 LOC | 5-10 min | Fast-track if passing CI |
| **Small** | 3-5 | 100-300 LOC | 15-30 min | Standard review |
| **Medium** | 5-10 | 300-600 LOC | 30-60 min | Thorough review |
| **Large** | 10+ | 600+ LOC | 60+ min | **Request split** if possible |

**Best Practice**: If PR is large (600+ LOC), ask author to split into logical smaller PRs

## 🔄 Review Workflow

### Step 1: Initial Check (2 min)
```
- PR template complete? ✅
- Title descriptive? ✅
- Risk level honest? ✅
- CI passing? ✅
```

### Step 2: Scope Assessment (3 min)
```
- Size appropriate? ✅
- Focus clear? ✅
- No scope creep? ✅
- Changes align with description? ✅
```

### Step 3: Code Review (varies)
- Security (HIGHEST priority)
- Multi-tenancy (HIGHEST priority)
- Functionality
- Quality
- Tests

### Step 4: Decision (1 min)
```
- Approve?
- Request changes?
- Comment only?
```

### Step 5: Follow-up
- Monitor for author responses
- Re-review if changes significant
- Approve when resolved

## 📝 Review Comment Templates

### Security Issue
```markdown
🚨 **Security Concern**: Multi-tenant isolation issue detected

This query doesn't filter by `tenant_id`:
```python
result = supabase.table("twins").select("*").execute()
```

Should be:
```python
result = supabase.table("twins").select("*").eq("tenant_id", user["tenant_id"]).execute()
```

See: `docs/ai/agent-manual.md` → "Multi-Tenant Filters"
```

### Logic Issue
```markdown
❓ **Logic Question**: Edge case handling

What happens if `user_id` is `None`? This could cause a silent failure:
```python
owner = users_map[user_id]  # KeyError if user_id not in map
```

Consider:
```python
owner = users_map.get(user_id)
if not owner:
    raise HTTPException(status_code=404, detail="User not found")
```
```

### Best Practice Suggestion
```markdown
💡 **Suggestion**: Follow project convention

Instead of:
```python
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
```

Use centralized client management:
```python
from modules.clients import get_openai_client
client = get_openai_client()
```

See: `backend/modules/clients.py`
```

### Test Coverage
```markdown
✋ **Test Coverage**: Missing coverage for error case

The happy path is tested, but what if the API call fails?

Consider adding:
```python
@pytest.mark.asyncio
async def test_chat_with_api_error():
    with patch('modules.clients.get_openai_client') as mock_client:
        mock_client.return_value.chat.completions.create.side_effect = Exception("API Error")
        response = await chat_endpoint(...)
        assert response.status_code == 500
```
```

### Architecture Impact
```markdown
⚠️ **Architecture Note**: Potential impact on RAG retrieval

This changes how context is retrieved. Please verify:
- [ ] Verified QnA matching still works
- [ ] Vector search fallback unaffected
- [ ] Tool invocation unchanged
- [ ] Tested with end-to-end retrieval flow

Reference: `modules/retrieval.py` (3-tier fallback logic)
```

## 👥 Review Assignment

### Lead Architect (Security/Architecture)
- Changes to critical files (`_core/`, `auth_guard.py`, etc.)
- Database schema changes
- API contract changes
- Multi-tenant isolation concerns

### Domain Expert (Feature Area)
- Backend features → Python expert
- Frontend features → TypeScript/React expert
- AI/ML features → LLM/RAG expert
- Infrastructure → DevOps expert

### Two Required for:
- Critical file changes
- Database migrations
- Security/auth changes
- Major refactoring (>500 LOC)

## 📊 Metrics to Track

### Code Review Health
- Average review time (target: < 4 hours)
- Reviewer turnaround (target: 24 hours)
- Approval rate (target: > 80%)
- Rework required (target: < 20%)
- Critical issues missed (target: 0)

### Code Quality Trends
- Bug escape rate (PRs that cause production issues)
- Security issues caught in review vs. production
- Test coverage over time
- Code duplication trends

## 🔗 Related Documents

- **PR Template**: `.github/PULL_REQUEST_TEMPLATE.md`
- **Coding Standards**: `.cursorrules`
- **Project Standards**: `docs/ai/agent-manual.md`
- **Architecture**: `docs/architecture/system-overview.md`
- **Quality Gate**: `docs/ops/QUALITY_GATE.md`
- **Known Issues**: `docs/KNOWN_FAILURES.md`

## ✅ Checklist for Reviewers

Before approving:
- [ ] All CI checks passing
- [ ] PR description complete and accurate
- [ ] No multi-tenant isolation violations
- [ ] No hardcoded secrets
- [ ] No circular imports or obvious bugs
- [ ] Test coverage reasonable for changes
- [ ] Code follows project conventions
- [ ] Backward compatibility maintained (or clearly breaking)
- [ ] Database migrations included (if schema changes)
- [ ] Comments/documentation updated
- [ ] Risk level assessment matches actual risk
- [ ] Rollback plan realistic and clear

## 🚀 Tips for Faster Reviews

1. **Keep PRs small** (< 400 LOC is ideal)
2. **Complete PR template** (no back-and-forth for missing info)
3. **Write descriptive commit messages** (helps reviewers understand intent)
4. **Link related issues** (provides context)
5. **Add screenshots/videos** (for UI changes)
6. **Self-review first** (catch obvious issues before submission)
7. **Run preflight locally** (ensure all checks pass)

## 🎓 Review Quality Standards

### Excellent Review
- Identifies security issues
- Suggests meaningful improvements
- Asks clarifying questions
- Provides learning opportunity
- Uses constructive tone

### Poor Review
- Only checks syntax
- Nitpicks style without reason
- Doesn't consider architecture
- Misses security issues
- Dismissive tone

---

**Remember**: Code review is about collaboration, not gatekeeping. The goal is to build better software together.
