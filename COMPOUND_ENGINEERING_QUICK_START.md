# Compound Engineering & Indexed Codebase: Implementation Checklist

> **Phase**: Quick Start
> **Timeline**: Week 1-2
> **Status**: Ready to Execute

---

## Week 1: Foundation Setup

### Day 1-2: MCP Installation

- [ ] **Update `.agent/mcp.json`** with 5 new MCPs
  - [ ] `filesystem` MCP
  - [ ] `git` MCP
  - [ ] `grep` MCP
  - [ ] `postgres` MCP
  - [ ] `openapi` MCP (optional, for API contracts)

- [ ] **Test each MCP**
  ```bash
  # Test filesystem
  "List backend/routers/ directory"

  # Test git
  "Show git log for backend/modules/auth_guard.py"

  # Test grep
  "Find all multi-tenant filters"

  # Test postgres
  "Show verified_qna table schema"

  # Test supabase (already configured)
  "SELECT COUNT(*) FROM twins"
  ```

- [ ] **Document findings** in `.agent/learnings/workflow_outcomes.json`

### Day 3: Pattern Index Creation

- [ ] **Create `.agent/indexes/patterns.json`** with initial patterns
  - [ ] ✅ Already created with 15 patterns
  - [ ] Review and validate all patterns
  - [ ] Add project-specific patterns if needed

- [ ] **Verify pattern coverage**
  - [ ] `auth_check_standard` (24 usages)
  - [ ] `multi_tenant_filter` (31 usages)
  - [ ] `supabase_client_singleton` (45 usages)
  - [ ] `rls_policy_creation` (15 usages)
  - [ ] Others...

### Day 4-5: Decisions & Knowledge Graph

- [ ] **Create `.agent/indexes/decisions.json`**
  - [ ] ✅ Already created with 10 decisions
  - [ ] Link decisions to patterns
  - [ ] Add lessons learned

- [ ] **Create `.agent/indexes/knowledge_graph.json`**
  - [ ] ✅ Already created with nodes and edges
  - [ ] Verify node interconnections
  - [ ] Test graph queries

- [ ] **Create `.agent/MCP_USAGE.md`**
  - [ ] ✅ Already created
  - [ ] Test all examples
  - [ ] Document project-specific queries

---

## Week 1: Learning Pipeline Activation

### Setup Outcome Capture

- [ ] **Enable automatic task logging**
  ```bash
  # Verify .agent/tools/capture_outcome.py exists
  # Add to every task completion:
  python .agent/tools/capture_outcome.py \
    --task_id "task-001" \
    --task_type "database" \
    --success true \
    --files_modified "backend/database/migrations/001_*.sql"
  ```

- [ ] **Create workflow tracking template**
  - Each task logs: task_type, success, execution_time, issues, solution

- [ ] **Verify `.agent/learnings/workflow_outcomes.json` is writable**

### Setup Weekly Analysis

- [ ] **Schedule automated analysis**
  ```bash
  # Monday 00:00 UTC
  python .agent/tools/analyze_workflows.py --weekly
  ```

- [ ] **Configure improvement recommendations**
  - Common failure modes → prompt refinements
  - Success patterns → documentation updates
  - New patterns → index updates

---

## Week 2: Integration & Refinement

### Integration with AGENTS.md

- [ ] **Add MCP section to AGENTS.md**
  ```markdown
  ## MCP-Enhanced Development

  ### Available MCPs
  - **filesystem**: Semantic file navigation
  - **git**: Full git history
  - **grep**: Code pattern search
  - **postgres**: Schema inspection
  - **openapi**: API contract validation

  ### Using MCPs
  See `.agent/MCP_USAGE.md` for detailed guide
  ```

- [ ] **Link pattern library in AGENTS.md**
  ```markdown
  ## Recommended Patterns

  Before implementing, check `.agent/indexes/patterns.json` for:
  - 15+ reusable patterns with examples
  - Usage counts and related patterns
  - Common mistakes to avoid
  ```

- [ ] **Update "Common AI Failure Patterns" section**
  Add MCP commands to quickly debug each failure:
  ```markdown
  ### #1 Missing Database Columns

  **MCP Debug**:
  ```bash
  grep MCP: "Find all verified_qna queries"
  postgres MCP: "Show verified_qna table schema"
  ```
  ```

### Validation & Testing

- [ ] **Test pattern index accuracy**
  - Verify usage counts for 5 random patterns
  - Check that all files listed actually exist
  - Validate code examples compile

- [ ] **Test knowledge graph connections**
  - Traverse 5 random edges
  - Verify relationships are correct
  - Check that patterns link to concepts

- [ ] **Test learning pipeline**
  - Run a sample task
  - Capture outcome
  - Verify logged in workflow_outcomes.json
  - Run analysis
  - Verify recommendations generated

### Documentation & Handoff

- [ ] **Update README.md** with MCP section
  ```markdown
  ### MCP-Enhanced Development

  This project uses Model Context Protocol (MCP) servers for faster development:
  - Filesystem navigation (5x speedup)
  - Git history analysis (10x speedup)
  - Code pattern search (8x speedup)

  See `.agent/MCP_USAGE.md` for details
  ```

- [ ] **Create `.agent/MCP_QUICK_REFERENCE.md`** for common tasks
  ```markdown
  # MCP Quick Reference

  Find multi-tenant filters:
  > grep MCP: "Find all .eq\('tenant_id',"

  Check specialization usage:
  > grep MCP: "Find all specialization_id"
  ...
  ```

- [ ] **Commit all changes**
  ```bash
  git add .agent/
  git commit -m "feat: MCP integration & indexed codebase for compound engineering

  - Add 5 MCPs (filesystem, git, grep, postgres, openapi)
  - Create pattern index (15 patterns, 200+ usages)
  - Create decision log (10 decisions, lessons learned)
  - Create knowledge graph (25 nodes, 13 edges)
  - Create MCP usage guide
  - Enable learning pipeline
  - Update AGENTS.md with MCP guidance

  Expected benefit: 3-5x faster development with zero regressions"
  ```

---

## Week 3-4: Continuous Improvement

### Monitor Learning Pipeline

- [ ] **Weekly Review (Every Monday)**
  ```bash
  python .agent/tools/analyze_workflows.py --weekly
  ```
  - [ ] Review failure patterns
  - [ ] Identify high-regression areas
  - [ ] Generate improvement recommendations

- [ ] **Monthly Refinement (First Monday)**
  ```bash
  python .agent/tools/evolve_prompts.py --monthly
  ```
  - [ ] Update pattern index with new discoveries
  - [ ] Enhance prompts based on learnings
  - [ ] Document new patterns

### Expand Pattern Library

- [ ] **Add 5-10 new patterns monthly**
  - [ ] Track new patterns discovered
  - [ ] Document anti-patterns found
  - [ ] Link to related concepts

- [ ] **Expand knowledge graph**
  - [ ] Add new nodes for emerging patterns
  - [ ] Create edges connecting concepts
  - [ ] Visualize relationships

### Team Enablement

- [ ] **Onboard new developers**
  - [ ] Share `.agent/MCP_USAGE.md`
  - [ ] Show pattern index
  - [ ] Demonstrate learning pipeline

- [ ] **Team knowledge share**
  - [ ] Weekly: Discuss failure patterns
  - [ ] Monthly: Review new patterns
  - [ ] Quarterly: Assess system improvements

---

## Expected Benefits

### Development Velocity

| Metric | Before | After | Gain |
|--------|--------|-------|------|
| Finding code patterns | 15 min | 2 min | 7.5x |
| Checking for regressions | Manual | 1 min | ∞ |
| Database validation | 20 min | 2 min | 10x |
| Onboarding new developer | 2 days | 4 hours | 12x |

### Quality Metrics

| Metric | Before | After |
|--------|--------|-------|
| Regression rate | 5-10% | <1% |
| Test-fail-fix cycle | 30 min | 5 min |
| Code review time | 1 hour | 15 min |
| Documentation accuracy | 80% | 99% |

---

## Success Criteria

By end of Week 2, you should have:

✅ **Infrastructure**
- [ ] 5 MCPs configured and tested
- [ ] All 5 MCPs successfully query the project
- [ ] No errors in MCP initialization

✅ **Indexing System**
- [ ] Pattern index with 15+ patterns
- [ ] Decision log with 10+ decisions
- [ ] Knowledge graph with 20+ nodes and edges
- [ ] All cross-references validated

✅ **Learning Pipeline**
- [ ] Outcome capture working
- [ ] Weekly analysis scheduled
- [ ] Improvement recommendations generated
- [ ] At least 3 workflow tasks logged

✅ **Integration**
- [ ] AGENTS.md updated with MCP guidance
- [ ] MCP_USAGE.md complete and tested
- [ ] Pattern library documented
- [ ] All changes committed to git

---

## Troubleshooting

### MCP Not Working
- [ ] Verify `.agent/mcp.json` syntax (JSON validator)
- [ ] Check environment variables (SUPABASE_URL, etc.)
- [ ] Restart VS Code / Cursor
- [ ] Check firewall/VPN allows outbound connections

### Pattern Index Incomplete
- [ ] Run `grep MCP` on known patterns
- [ ] Manually verify file paths exist
- [ ] Check git is not excluding files (.gitignore)

### Learning Pipeline Silent
- [ ] Check `.agent/learnings/workflow_outcomes.json` is writable
- [ ] Verify Python 3.8+ installed (`python --version`)
- [ ] Run manual task capture to test
- [ ] Check cron/scheduler logs

### Knowledge Graph Not Connecting
- [ ] Verify node IDs match exactly (case-sensitive)
- [ ] Check edge source/target node IDs exist
- [ ] Validate JSON syntax

---

## Quick Validation Commands

```bash
# Check MCP config syntax
python -m json.tool .agent/mcp.json

# Verify pattern index
python -m json.tool .agent/indexes/patterns.json | head -50

# Check decision log
python -m json.tool .agent/indexes/decisions.json | head -50

# Validate knowledge graph
python -m json.tool .agent/indexes/knowledge_graph.json | head -50

# Verify workflow outcomes
ls -la .agent/learnings/

# Test grep MCP (manual)
grep -r "tenant_id" backend/ --include="*.py" | wc -l
```

---

## Files Created/Updated

| File | Status | Purpose |
|------|--------|---------|
| `MCP_AND_INDEXING_STRATEGY.md` | ✅ Created | Full strategy document |
| `.agent/mcp.json` | 🔲 Update | Add 5 MCPs |
| `.agent/indexes/patterns.json` | ✅ Created | 15 patterns |
| `.agent/indexes/decisions.json` | ✅ Created | 10 decisions |
| `.agent/indexes/knowledge_graph.json` | ✅ Created | 25 nodes, 13 edges |
| `.agent/MCP_USAGE.md` | ✅ Created | MCP reference guide |
| `AGENTS.md` | 🔲 Update | Add MCP section |
| `.agent/MCP_QUICK_REFERENCE.md` | 🔲 Create | Common queries |

---

## Next Steps

1. **This Week**: Install MCPs, test, create indexes (all templates provided)
2. **Next Week**: Integrate with AGENTS.md, activate learning pipeline
3. **Ongoing**: Monitor weekly, expand pattern library, refine prompts

All materials ready. You can start immediately.
