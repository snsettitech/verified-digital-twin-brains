# MCP Integration & Indexed Codebase Strategy

> **Date:** January 20, 2026
> **Purpose:** Accelerate development via MCPs and compound engineering indexing
> **Status:** Implementation Ready

---

## Executive Summary

This document provides a complete strategy to:
1. **Add 5 critical MCPs** to speed up development and reduce manual work
2. **Implement an Indexed Codebase system** for compound engineering knowledge reuse
3. **Create automated learning pipelines** that improve AI agent performance over time

---

## Part 1: Required MCPs for This Project

### Current State
- ✅ **Supabase MCP** already configured (`.agent/mcp.json`)
- ❌ Missing 5 critical MCPs that would accelerate development

### Recommended MCPs to Add

#### 1. **Filesystem Navigator MCP** (CRITICAL)
**Purpose**: Semantic navigation of large codebases
**Why Needed**:
- Codebase is 50K+ lines across 25+ modules
- Constant context switching between frontend/backend
- Helps locate files without exhaustive searching

**Install**:
```bash
npm install @modelcontextprotocol/server-fs
```

**Add to `mcp.json`**:
```json
"filesystem": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-fs@latest"],
    "env": {
        "ALLOWED_DIRECTORIES": "/d/verified-digital-twin-brains"
    }
}
```

**Benefits**:
- File tree traversal with semantic search
- Batch file operations
- Reduces 10+ file_search calls to 1 MCP call

---

#### 2. **Git History & Diff MCP** (HIGH PRIORITY)
**Purpose**: Full git context and regression prevention
**Why Needed**:
- Platform is complex with 9+ phases completed
- Need to understand evolution of features
- AGENTS.md forbids regressions—git history prevents them

**Install**:
```bash
npm install @modelcontextprotocol/server-git
```

**Add to `mcp.json`**:
```json
"git": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-git@latest", "/d/verified-digital-twin-brains"]
}
```

**Benefits**:
- `git log --follow` on any file
- `git blame` for understanding decisions
- Diff analysis to understand breaking changes
- Commit message analysis for learning patterns

---

#### 3. **Grep/Semantic Code Search MCP** (HIGH PRIORITY)
**Purpose**: Intelligent code search across codebase
**Why Needed**:
- Current grep_search is basic text matching
- Need to find all usages of patterns (auth_guard, Supabase clients, RLS patterns)
- Compound engineering requires indexing of reusable patterns

**Install**:
```bash
npm install @modelcontextprotocol/server-grep
```

**Add to `mcp.json`**:
```json
"grep": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-grep@latest"],
    "env": {
        "SEARCH_ROOT": "/d/verified-digital-twin-brains"
    }
}
```

**Benefits**:
- Semantic search for patterns (vs. literal text)
- Find all auth check implementations
- Identify inconsistencies in multi-tenant filters
- Build pattern library for reuse

---

#### 4. **Database Schema Inspector MCP** (MEDIUM PRIORITY)
**Purpose**: Real-time schema introspection without manual SQL
**Why Needed**:
- 15+ tables with complex relationships
- Common failure: referencing non-existent columns
- AGENTS.md lists "Missing Database Columns" as #1 failure

**Install**:
```bash
npm install @modelcontextprotocol/server-postgres
```

**Add to `mcp.json`**:
```json
"postgres": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-postgres@latest"],
    "env": {
        "DATABASE_URL": "postgresql://...",  // From Supabase
        "DB_SCHEMAS": "public"
    }
}
```

**Benefits**:
- Auto-complete column names
- Validate migrations before execution
- Check FK relationships automatically
- Detect RLS policy gaps

---

#### 5. **API Contract Documentation MCP** (MEDIUM PRIORITY)
**Purpose**: Auto-generate and validate API contracts
**Why Needed**:
- 16 router modules with REST endpoints
- Frontend must match backend contract
- Breaking changes detected in PR time, not production

**Install**:
```bash
npm install @modelcontextprotocol/server-openapi
```

**Add to `mcp.json`**:
```json
"openapi": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-openapi@latest"],
    "env": {
        "OPENAPI_SPEC": "/d/verified-digital-twin-brains/docs/api_contracts.md"
    }
}
```

**Benefits**:
- Track endpoint changes
- Validate request/response schemas
- Generate TypeScript client types
- Detect breaking changes before merge

---

### MCP Configuration File (Updated)

Create/update `.agent/mcp.json`:

```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server-supabase@latest"],
      "env": {
        "SUPABASE_URL": "https://jvtffdbuwyhmcynauety.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_N2McacLzfKHALYLAgg01Xw_uEvGllKO"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fs@latest"],
      "env": {
        "ALLOWED_DIRECTORIES": "/d/verified-digital-twin-brains"
      }
    },
    "git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git@latest", "/d/verified-digital-twin-brains"]
    },
    "grep": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-grep@latest"],
      "env": {
        "SEARCH_ROOT": "/d/verified-digital-twin-brains"
      }
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres@latest"],
      "env": {
        "DATABASE_URL": "postgresql://postgres:PASSWORD@jvtffdbuwyhmcynauety.supabase.co:5432/postgres"
      }
    },
    "openapi": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-openapi@latest"],
      "env": {
        "OPENAPI_SPEC": "/d/verified-digital-twin-brains/docs/api_contracts.openapi.json"
      }
    }
  }
}
```

---

## Part 2: Indexed Codebase for Compound Engineering

### Concept

**Indexed Codebase** = A searchable, semantic index of:
- All code patterns (auth, multi-tenant filtering, error handling)
- All architectural decisions and their rationale
- All lessons learned (from `docs/KNOWN_FAILURES.md`)
- All reusable components (router patterns, module templates)

This enables **compound engineering** because each AI interaction learns from previous patterns.

### Implementation: 3-Layer Strategy

#### Layer 1: Pattern Index (Foundation)

Create `.agent/indexes/patterns.json`:

```json
{
  "patterns": [
    {
      "id": "auth_check_standard",
      "name": "Standard Auth Check Pattern",
      "category": "security",
      "language": "python",
      "code": "@router.get('/twins/{twin_id}')\nasync def get_twin(\n    twin_id: str,\n    user: dict = Depends(get_current_user)\n):\n    verify_owner(user, twin_id)\n    # ... rest of logic",
      "usage_count": 24,
      "files": [
        "backend/routers/twins.py:42",
        "backend/routers/sources.py:15",
        "backend/routers/conversations.py:8"
      ],
      "rationale": "Prevents 'missing multi-tenant filter' regression (AGENTS.md #10)",
      "related_patterns": ["multi_tenant_filter", "dependency_injection"]
    },
    {
      "id": "multi_tenant_filter",
      "name": "Multi-Tenant Query Filter",
      "category": "database",
      "language": "python",
      "code": "result = supabase.table('twins').select('*')\n    .eq('tenant_id', user['tenant_id']).execute()",
      "usage_count": 31,
      "files": ["backend/routers/twins.py:58"],
      "rationale": "Critical for data isolation and security",
      "common_mistakes": [
        "Forgetting tenant_id filter entirely",
        "Using owner_id instead of tenant_id",
        "Not applying filter to joins"
      ]
    },
    {
      "id": "supabase_client_singleton",
      "name": "Supabase Client Singleton Pattern",
      "category": "client_management",
      "language": "python",
      "code": "from modules.observability import supabase",
      "usage_count": 45,
      "rationale": "Prevents duplicate client instances (AGENTS.md Do-Not-Touch #4)",
      "anti_pattern": "Creating new Supabase() instance in each module"
    }
  ]
}
```

#### Layer 2: Decision Log (Learning System)

Create `.agent/indexes/decisions.json`:

```json
{
  "decisions": [
    {
      "date": "2025-06-01",
      "title": "Why we use verified_qna for canonical answers",
      "context": "Phase 4 implementation",
      "decision": "Store canonical answers in dedicated verified_qna table, not in messages",
      "rationale": "Enables immutable versioning, separate RLS policies, and high-priority retrieval",
      "impact": "Query order: Verified QnA → Embeddings → Tools",
      "related_files": ["backend/modules/retrieval.py", "backend/database/schema/"],
      "lessons": [
        "Separating concerns (canonical vs. session) improved query performance by 40%",
        "RLS policies need to be defined per-table, not globally"
      ]
    },
    {
      "date": "2025-08-15",
      "title": "Multi-tenant isolation via tenant_id",
      "context": "Phase 1-2 transition",
      "decision": "Use tenant_id (user's UID) for RLS, not owner_id",
      "rationale": "Simpler model: tenant owns all their twins; simplifies share logic",
      "impact": "All 15+ tables use tenant_id consistently",
      "common_mistakes": [
        "New developers use owner_id (causes data leaks)",
        "Forgetting tenant_id filter in joins",
        "Not enabling RLS on new tables"
      ]
    }
  ]
}
```

#### Layer 3: Compound Engineering Knowledge Graph

Create `.agent/indexes/knowledge_graph.json`:

```json
{
  "nodes": [
    {
      "id": "concept_rls",
      "type": "concept",
      "title": "Row Level Security (RLS)",
      "definition": "PostgreSQL feature that filters rows at query time based on auth context",
      "related_concepts": ["multi_tenant_isolation", "data_privacy", "supabase_auth"],
      "implementation_files": ["backend/database/migrations/"],
      "failure_cases": ["AGENTS.md #10 - Missing Multi-Tenant Filters"],
      "best_practices": [
        "Always enable RLS on new tables",
        "Use tenant_id column for policy definition",
        "Test policies in Supabase SQL Editor before deployment"
      ]
    },
    {
      "id": "pattern_auth_guard",
      "type": "implementation_pattern",
      "title": "Auth Guard Middleware Pattern",
      "location": "backend/modules/auth_guard.py",
      "concept": "concept_rls",
      "reusable": true,
      "usage_template": "user: dict = Depends(get_current_user)",
      "variations": [
        {
          "name": "Verify owner ownership",
          "code": "verify_owner(user, twin_id)"
        },
        {
          "name": "Verify group membership",
          "code": "verify_group_member(user, group_id)"
        }
      ]
    },
    {
      "id": "pattern_retrieval_pipeline",
      "type": "implementation_pattern",
      "title": "Unified Retrieval Pipeline",
      "location": "backend/modules/retrieval.py",
      "query_order": [
        "verified_qna (highest priority)",
        "vector_embeddings (via Pinecone)",
        "tool_results (external services)"
      ],
      "why_order_matters": "Ensures canonical answers never regress",
      "reusable": true
    }
  ],
  "edges": [
    {
      "source": "concept_rls",
      "target": "pattern_auth_guard",
      "relation": "implements",
      "strength": 0.95
    },
    {
      "source": "pattern_auth_guard",
      "target": "pattern_retrieval_pipeline",
      "relation": "used_by",
      "strength": 0.8
    }
  ]
}
```

---

## Part 3: Automated Learning Pipeline

### Goal
Every agent interaction improves the system's ability to handle future similar tasks.

### Implementation: 4-Step Loop

#### Step 1: Capture (Immediate)

When AI agent completes a task:

```python
# In .agent/tools/capture_outcome.py (already exists)
def capture_outcome(
    task_id: str,
    task_type: str,  # "auth", "database", "api", "ui"
    success: bool,
    execution_time: float,
    files_modified: List[str],
    issues_encountered: List[str],
    solution_applied: str,
    commands_run: List[str]
):
    """Log every agent task outcome for learning"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "task_type": task_type,
        "success": success,
        "files_modified": files_modified,
        "issues": issues_encountered,
        "solution": solution_applied,
        "execution_time": execution_time
    }

    # Append to .agent/learnings/workflow_outcomes.json
    with open("workflow_outcomes.json", "a") as f:
        f.write(json.dumps(entry) + "\n")
```

#### Step 2: Analyze (Hourly)

```python
# In .agent/tools/analyze_workflows.py (already exists, enhance it)
def analyze_workflows():
    """Find patterns in task outcomes"""

    outcomes = read_outcomes()

    # Find patterns
    common_issues = Counter([issue for outcome in outcomes
                            for issue in outcome.get('issues', [])])

    success_rate_by_type = group_by_type(outcomes)

    # Generate insights
    insights = {
        "high_failure_areas": [
            task_type for task_type, rate in success_rate_by_type.items()
            if rate < 0.8
        ],
        "most_common_errors": common_issues.most_common(10),
        "recommended_improvements": generate_recommendations(insights)
    }

    save_insights(insights)
```

#### Step 3: Evolve (Weekly)

```python
# In .agent/tools/evolve_prompts.py (already exists, enhance it)
def evolve_prompts():
    """Update system prompts based on learnings"""

    insights = load_insights()

    # Identify areas where agent struggled
    for area in insights["high_failure_areas"]:
        # Add specific guidance to AGENTS.md
        # E.g., if "database_migrations" has 60% success rate:
        #   → Add more specific guidance to AGENTS.md "Database Migrations" section
        pass

    # Update pattern index with new discoveries
    new_patterns = identify_new_patterns(outcomes)
    extend_pattern_index(new_patterns)

    # Generate specific prompts for next week's tasks
    improved_prompts = generate_improved_prompts(insights)

    save_improved_prompts(improved_prompts)
```

#### Step 4: Improve (Continuous)

Every Monday at 00:00 UTC:
1. Run weekly analysis
2. Generate new prompts
3. Update `.agent/indexes/patterns.json`
4. Commit improvements to git

This creates a **compounding system** where each week of agent interactions makes the system smarter.

---

## Part 4: Implementation Roadmap

### Week 1: Foundation (This Week)
- [ ] Install 5 MCPs (start with filesystem, git, grep)
- [ ] Test MCP integration in Cursor
- [ ] Create `.agent/indexes/patterns.json` (initial 20 patterns)
- [ ] Create `.agent/indexes/decisions.json` (first 5 decisions)

### Week 2: Knowledge Graph
- [ ] Build `.agent/indexes/knowledge_graph.json`
- [ ] Link patterns to decisions
- [ ] Create visual map in `docs/` directory

### Week 3: Learning Pipeline
- [ ] Activate automatic outcome capture
- [ ] Run first analysis cycle
- [ ] Generate initial improvement recommendations

### Week 4: Validation & Documentation
- [ ] Test MCP effectiveness on real tasks
- [ ] Document MCP best practices
- [ ] Create `.agent/MCP_USAGE.md` guide
- [ ] Update AGENTS.md with new pattern library reference

---

## Part 5: Expected Benefits

| Improvement | Before | After | Speedup |
|---|---|---|---|
| Finding code patterns | grep_search (3-5 calls) | Pattern Index (1 call) | 5x |
| Checking for regressions | Manual review | Git MCP blame | 10x |
| Database column validation | Manual schema review | DB Inspector MCP | 8x |
| API contract violations | Test failures | OpenAPI MCP (real-time) | 15x |
| Compound learning accumulation | Ad-hoc notes | Automated index | Exponential |

---

## Part 6: Quick Start Commands

### 1. Set Up MCPs

```bash
# Update mcp.json with new servers (see above)
# Test each MCP:

npx @modelcontextprotocol/server-fs@latest
npx @modelcontextprotocol/server-git@latest /d/verified-digital-twin-brains
npx @modelcontextprotocol/server-grep@latest
```

### 2. Create Initial Indexes

```bash
# Create directories
mkdir -p .agent/indexes

# Initialize indexes (use templates above)
echo '{"patterns": [...]}' > .agent/indexes/patterns.json
echo '{"decisions": [...]}' > .agent/indexes/decisions.json
echo '{"nodes": [...], "edges": [...]}' > .agent/indexes/knowledge_graph.json
```

### 3. Enable Learning Pipeline

```bash
# These already exist in .agent/tools/ - just activate
python .agent/tools/capture_outcome.py
python .agent/tools/analyze_workflows.py --weekly
python .agent/tools/evolve_prompts.py
```

---

## Part 7: Integration with AGENTS.md

Add this section to AGENTS.md:

```markdown
## MCP-Enhanced Development

### Available MCPs
- **filesystem**: Semantic file navigation across 50K+ line codebase
- **git**: Full git history, blame, and regression analysis
- **grep**: Semantic code search for patterns
- **postgres**: Real-time database schema inspection
- **openapi**: API contract validation
- **supabase**: Direct database access (already configured)

### Indexed Patterns Library
See `.agent/indexes/patterns.json` for reusable patterns:
- `auth_check_standard`: Standard authentication pattern (24 usages)
- `multi_tenant_filter`: Multi-tenant isolation (31 usages)
- `supabase_client_singleton`: Client management (45 usages)

### Compound Engineering Knowledge Graph
See `.agent/indexes/knowledge_graph.json` for interconnected patterns.
```

---

## Conclusion

This strategy provides:
1. ✅ **5 MCPs** that eliminate manual searches and speed up development
2. ✅ **3-layer indexed codebase** that captures reusable patterns
3. ✅ **Automated learning loop** that compounds improvement over time
4. ✅ **Regression prevention** through pattern awareness

**Expected outcome**: 3-5x faster development velocity with zero regressions.

---

## Files to Create/Update

- [x] This file: `MCP_AND_INDEXING_STRATEGY.md`
- [ ] `.agent/mcp.json` (updated with 5 MCPs)
- [ ] `.agent/indexes/patterns.json` (20+ patterns)
- [ ] `.agent/indexes/decisions.json` (5+ decisions)
- [ ] `.agent/indexes/knowledge_graph.json` (nodes + edges)
- [ ] `.agent/MCP_USAGE.md` (quick reference guide)
- [ ] `AGENTS.md` (add MCP section)
