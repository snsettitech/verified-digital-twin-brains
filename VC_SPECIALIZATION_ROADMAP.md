# VC Specialization Roadmap

> **Scope:** Assets and configuration only.  
> **Platform Dependency:** Phase 3.5 (Cognitive Brain Builder) must be complete first.  
> **No new core logic** unless explicitly approved by platform owner.

---

## Status Legend

- `✅ DONE` — Asset exists and is loadable
- `🟡 STUB` — Partial or placeholder content
- `⬜ NOT STARTED` — Absent from codebase

---

## Platform Dependency

> [!IMPORTANT]
> VC specialization cannot function until Platform Phase 3.5 gates are complete.

| Platform Gate | Required For | Status |
|---------------|--------------|--------|
| Per-Twin Specialization | Manifest loading per twin | ✅ DONE |
| Real Tenant Guard | Secure VC data isolation | ✅ DONE |
| Supabase Graph Persistence | Store VC cognitive graph | ✅ DONE |
| End-to-End Interview Loop | VC interview flow | ✅ DONE |
| Approval Versioning | VC profile approval | ✅ DONE |
| Playwright E2E | VC tenant isolation proof | ✅ DONE |

---

## VC Specialization Scope

The VC Brain specialization consists of **configuration files and JSON assets only**:

```
backend/modules/specializations/vc/
├── manifest.json         # Central config (packs, prompts, feature flags)
├── host_policy.json      # Slot priority, cluster ordering, follow-up behavior
├── default_triggers.json # VC-specific event triggers
├── ontology/
│   └── vc_base_pack.json # Node types, edge types, constraints
└── prompts/
    └── host_prompt.txt   # VC interview tone and style

frontend/src/specializations/vc/
└── ui_clusters.json      # Cluster display config for UI
```

---

## Phase A: VC Assets (Configuration Layer)

### A.1 VC Base Pack — **✅ DONE**

| Asset | Status | Location |
|-------|--------|----------|
| `vc_base_pack.json` | ✅ DONE | `ontology/vc_base_pack.json` |
| Node types (thesis, rubric, moat, process, comms) | ✅ DONE | In pack |
| Edge types (DEPENDS_ON, IMPLIES, etc.) | 🟡 STUB | Defined in pack, not validated |

**Next Steps:**
- [ ] Add validation constraints per node type
- [ ] Define 40-60 question templates

---

### A.2 Question Templates — **⬜ NOT STARTED**

**Goal:** 40-60 natural-language question templates for the Host to paraphrase.

| Template Category | Target Count | Status |
|-------------------|--------------|--------|
| Thesis cluster | 10-15 | ⬜ NOT STARTED |
| Rubric cluster | 10-15 | ⬜ NOT STARTED |
| Moat cluster | 8-10 | ⬜ NOT STARTED |
| Process cluster | 8-10 | ⬜ NOT STARTED |
| Comms cluster | 5-8 | ⬜ NOT STARTED |

**Deliverable:** `templates/vc_questions.json` → **Integrated into `vc_base_pack.json`**

**Status: ✅ DONE** — 53 question templates across all clusters

| Template Category | Target Count | Actual | Status |
|-------------------|--------------|--------|--------|
| Identity cluster | 10-12 | 10 | ✅ DONE |
| Thesis cluster | 10-15 | 10 | ✅ DONE |
| Rubric cluster | 10-15 | 12 | ✅ DONE |
| Moat cluster | 8-10 | 7 | ✅ DONE |
| Process cluster | 8-10 | 7 | ✅ DONE |
| Comms cluster | 5-8 | 7 | ✅ DONE |

---

### A.3 Extension Packs — **✅ DONE (DeepTech)**

**Goal:** Optional ontology extensions for specific VC focus areas.

| Pack | Max Nodes | Max Edges | Max Templates | Status |
|------|-----------|-----------|---------------|--------|
| DeepTech | 8 | — | 15 | ✅ DONE |
| Climate | 25 | 40 | 30 | ⬜ NOT STARTED |
| Consumer | 25 | 40 | 30 | ⬜ NOT STARTED |

**Extension Pack Schema:**
```json
{
  "id": "deeptech",
  "extends": "vc_base",
  "nodes": [...],
  "edges": [...],
  "templates": [...]
}
```

---

### A.4 Cluster Summaries Config — **✅ DONE**

| Asset | Status | Location |
|-------|--------|----------|
| `ui_clusters.json` | ✅ DONE | `frontend/src/specializations/vc/ui_clusters.json` |
| Cluster-to-node mappings | ✅ DONE | 7 clusters with primary_nodes |
| Summary generation prompts | ✅ DONE | summary_prompt per cluster |

**Next Steps:**
- [ ] Map each cluster to its node types
- [ ] Define summary prompt template per cluster

---

### A.5 VC Host Policy — **✅ DONE**

| Asset | Status | Location |
|-------|--------|----------|
| `host_policy.json` | ✅ DONE | `backend/modules/specializations/vc/host_policy.json` |
| Required slots | ✅ DONE | In policy |
| Cluster ordering | ✅ DONE | In policy |
| Follow-up behavior | ✅ DONE | In policy |

---

### A.6 VC Triggers — **✅ DONE**

| Asset | Status | Location |
|-------|--------|----------|
| `default_triggers.json` | ✅ DONE | `backend/modules/specializations/vc/default_triggers.json` |
| Event types | ✅ DONE | In triggers |
| Action mappings | ✅ DONE | In triggers |

---

## Definition of Done: VC Specialization

| Criteria | Status |
|----------|--------|
| VC Base Pack loadable via platform ontology_loader | ✅ DONE |
| Manifest contains inline feature_flags | ✅ DONE |
| Host policy is structured JSON (not in prompts) | ✅ DONE |
| 40-60 question templates defined | ✅ DONE (53 templates) |
| At least 1 extension pack (DeepTech) created | ✅ DONE |
| UI clusters mapped to node types | ✅ DONE |

---

## Current Focus

> [!NOTE]
> **VC Specialization is COMPLETE!** All Definition of Done criteria met.

**Completed:**
1. ✅ A.2 Question Templates (53 total)
2. ✅ A.3 DeepTech Extension Pack
3. ✅ A.4 Cluster-to-Node Mappings

**Optional Future Work:**
- Climate Extension Pack
- Consumer Extension Pack

---

## Out of Scope for VC Specialization

The following are **platform concerns**, not VC specialization work:

- ❌ Tenant isolation logic (→ Platform Gate 2)
- ❌ Graph persistence tables (→ Platform Gate 3)
- ❌ Scribe LLM integration (→ Platform Gate 4)
- ❌ Approval versioning (→ Platform Gate 5)
- ❌ E2E tests (→ Platform Gate 6)

Any request to add these to VC roadmap should be redirected to `PLATFORM_ROADMAP.md`.
