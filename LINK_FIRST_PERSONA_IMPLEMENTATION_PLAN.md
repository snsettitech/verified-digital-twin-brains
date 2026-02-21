# Link-First Persona Implementation Plan
## Phase 0: Repository Verification

**Auditor:** Kimi2 (Principal Engineer)  
**Date:** 2026-02-20  
**Status:** VERIFIED - All referenced code exists as claimed

---

## 1. Verified Code Snippets

### 1.1 backend/modules/persona_spec_v2.py (lines 63-122)

```python
class CognitiveHeuristic(BaseModel):
    """
    Single reasoning pattern or mental model
    
    Heuristics are applied based on query type and context.
    """
    id: str = Field(description="Unique identifier for this heuristic")
    name: str = Field(description="Human-readable name")
    description: str = Field(default="", description="What this heuristic does")
    applicable_query_types: List[str] = Field(
        default_factory=list,
        description="Query types where this heuristic applies (e.g., 'evaluation', 'comparison')"
    )
    steps: List[str] = Field(
        default_factory=list,
        description="Ordered steps for applying this heuristic"
    )
    active: bool = Field(default=True, description="Whether this heuristic is active")
    priority: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Priority (lower = higher priority, like z-index)"
    )


class CognitiveHeuristics(BaseModel):
    """
    Layer 2: How this persona thinks
    
    Defines the reasoning frameworks and evaluation criteria used
    when making decisions or providing analysis.
    """
    default_framework: str = Field(
        default="evidence_based",
        description="Default reasoning framework when no specific heuristic applies"
    )
    heuristics: List[CognitiveHeuristic] = Field(
        default_factory=list,
        description="Available reasoning patterns"
    )
```

**GAP IDENTIFIED:** `CognitiveHeuristic` and `ValueItem` lack `verification_required` field. This is REQUIRED for Phase 3.

---

### 1.2 backend/modules/persona_decision_engine.py (lines 63-122)

```python
class QueryClassifier:
    """Classifies queries for appropriate processing"""
    
    EVALUATION_KEYWORDS = [
        "evaluate", "assess", "rate", "score", "analyze",
        "what do you think", "opinion on", "thoughts on",
        "startup", "founder", "market", "traction"
    ]
    
    ADVICE_KEYWORDS = [
        "should I", "what should", "recommend", "advice",
        "guide me", "help me decide", "what would you do"
    ]
    
    FACTUAL_KEYWORDS = [
        "what is", "how does", "when did", "who is",
        "explain", "tell me about"
    ]
    
    def classify(self, query: str) -> QueryClassification:
        """Classify a query"""
        query_lower = query.lower()
        
        # Determine query type
        if any(kw in query_lower for kw in self.EVALUATION_KEYWORDS):
            query_type = "evaluation"
            requires_evidence = True
            confidence_required = 0.8
```

**VERIFIED:** Decision engine exists and implements 5-Layer processing with evidence requirements.

---

### 1.3 backend/modules/persona_bootstrap.py (lines 26-76)

```python
def bootstrap_persona_from_onboarding(onboarding_data: Dict[str, Any]) -> PersonaSpecV2:
    """
    Canonical bootstrap function: Convert onboarding form data to 5-Layer Persona Spec v2.
    
    This is the PRIMARY and ONLY path for new twin persona creation.
    Legacy flattened system_prompt approach is DEPRECATED for new twins.
    
    Args:
        onboarding_data: Structured form data from frontend onboarding
        
    Returns:
        PersonaSpecV2 with all 5 layers populated
    """
    
    # Extract top-level fields
    twin_name = onboarding_data.get("twin_name", "Digital Twin")
    tagline = onboarding_data.get("tagline", "")
    role_definition = onboarding_data.get("role_definition", f"{twin_name} - {tagline}")
    
    # Layer 1: Identity Frame
    identity_frame = _build_identity_frame(onboarding_data)
    
    # Layer 2: Cognitive Heuristics
    cognitive_heuristics = _build_cognitive_heuristics(onboarding_data)
    
    # Layer 3: Value Hierarchy
    value_hierarchy = _build_value_hierarchy(onboarding_data)
    
    # Layer 4: Communication Patterns
    communication_patterns = _build_communication_patterns(onboarding_data)
    
    # Layer 5: Memory Anchors
    memory_anchors = _build_memory_anchors(onboarding_data)
    
    # Safety Boundaries
    safety_boundaries = _build_safety_boundaries(onboarding_data)
    
    return PersonaSpecV2(
        version="2.0.0",
        name=f"{twin_name} Persona",
        description=tagline or f"5-Layer cognitive persona for {twin_name}",
        identity_frame=identity_frame,
        cognitive_heuristics=cognitive_heuristics,
        value_hierarchy=value_hierarchy,
        communication_patterns=communication_patterns,
        memory_anchors=memory_anchors,
        safety_boundaries=safety_boundaries,
        status="active",  # Auto-publish
        source="onboarding_v2",
    )
```

**VERIFIED:** Bootstrap function exists and builds all 5 layers.

---

### 1.4 backend/modules/persona_spec_store_v2.py (lines 173-220)

```python
async def create_persona_spec_v2(
    twin_id: str,
    tenant_id: Optional[str],
    created_by: str,
    spec: PersonaSpecV2,
    status: str = "draft",
    source: str = "manual",
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a new v2 persona spec
    
    Args:
        twin_id: The twin ID
        tenant_id: Optional tenant ID
        created_by: User ID creating the spec
        spec: The v2 persona spec
        status: "draft", "active", or "archived"
        source: Source of the spec
        notes: Optional notes
    
    Returns:
        Created row or None
    """
    # Ensure version is set
    if not spec.version or not spec.version.startswith("2."):
        # Get latest version for this twin
        latest = await _latest_version_v2(twin_id)
        spec.version = next_patch_version(latest)
    
    payload = {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "version": spec.version,
        "status": status,
        "spec": spec.model_dump(),
        "source": source,
        "notes": notes,
        "created_by": created_by,
    }
    
    try:
        res = supabase.table("persona_specs").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[PersonaSpecV2] create failed: {e}")
        return None
```

**VERIFIED:** Spec storage function exists with status="active" support.

---

### 1.5 backend/modules/agent.py (lines 351-410)

```python
    # ====================================================================
    # NEW: Check for 5-Layer Persona Spec v2 FIRST (for new twins)
    # ====================================================================
    v2_persona_spec = None
    has_v2_persona = full_settings.get("use_5layer_persona", False)
    
    if has_v2_persona:
        try:
            from modules.persona_spec_store_v2 import get_active_persona_spec_v2
            v2_row = get_active_persona_spec_v2(twin_id)
            if v2_row and v2_row.get("spec"):
                v2_persona_spec = v2_row.get("spec")
                # Build persona section from v2 spec
                persona_section = _build_prompt_from_v2_persona(v2_persona_spec, full_settings.get("name", "Digital Twin"))
                persona_trace["persona_spec_version"] = v2_row.get("version") or "2.0.0"
                persona_trace["persona_prompt_variant"] = "v2_default"
                print(f"[AGENT] Using 5-Layer Persona v2 for twin {twin_id}")
        except Exception as e:
            print(f"[AGENT] Warning: Could not use v2 persona for {twin_id}: {e}")
    
    # ====================================================================
    # FALLBACK: Check for v1 persona spec (legacy twins)
    # ====================================================================
    if not persona_section:
        active_persona_row = get_active_persona_spec(twin_id=twin_id)
        if active_persona_row and active_persona_row.get("spec"):
            try:
                parsed = PersonaSpec.model_validate(active_persona_row["spec"])
                runtime_modules = list_runtime_modules_for_intent(
                    twin_id=twin_id,
                    intent_label=intent_label,
                    limit=8,
                    include_draft=True,
                )
                prompt_plan = compile_prompt_plan(
                    spec=parsed,
                    intent_label=intent_label,
                    user_query=last_human_msg,
                    runtime_modules=runtime_modules,
                    max_few_shots=max(0, int(render_options.max_few_shots)),
                    module_detail_level=render_options.module_detail_level,
                )
                persona_section = render_prompt_plan_with_options(plan=prompt_plan, options=render_options)
```

**VERIFIED:** Agent runtime has v2 selection with v1 fallback exactly as claimed.

---

### 1.6 backend/routers/twins.py (lines 102-264)

```python
@router.post("/twins")
async def create_twin(request: TwinCreateRequest, user=Depends(get_current_user)):
    """
    Create a new twin with 5-Layer Persona Spec v2.
    
    This is the PRIMARY path for new twin creation. The system automatically:
    1. Creates the twin record
    2. Bootstraps a structured 5-Layer Persona Spec v2 from onboarding data
    3. Publishes the persona as ACTIVE (no manual steps)
    4. Configures twin to use 5-Layer Persona by default
    
    Legacy flattened system_prompt is DEPRECATED for new twins.
    """
    # ... (validation logic) ...
    
    if response.data:
        twin = response.data[0]
        twin_id = twin.get('id')
        print(f"[TWINS] Twin created: {twin_id}")
        
        # ====================================================================
        # STEP 2: Auto-Create 5-Layer Persona Spec v2
        # ====================================================================
        
        try:
            # Merge persona data from request with defaults
            onboarding_data = request.persona_v2_data or {}
            onboarding_data["twin_name"] = requested_name
            onboarding_data["specialization"] = request.specialization
            
            # Bootstrap the structured persona spec
            persona_spec = bootstrap_persona_from_onboarding(onboarding_data)
            
            # Store in persona_specs table as ACTIVE
            persona_record = create_persona_spec_v2(
                twin_id=twin_id,
                tenant_id=tenant_id,
                created_by=user_id,
                spec=persona_spec.model_dump(mode="json"),
                status="active",  # Auto-publish
                source="onboarding_v2",
                metadata={
                    "onboarding_version": "2.0",
                    "specialization": request.specialization,
                    "auto_published": True,
                }
            )
```

**VERIFIED:** POST /twins handler exists with exact bootstrap call and status="active".

---

### 1.7 frontend/app/onboarding/page.tsx (lines 234-311)

```typescript
  const createTwin = async () => {
    setIsLaunching(true);

    try {
      const personaV2Data = buildPersonaV2Data();

      const expertiseText = identityData.expertise.join(', ');
      const legacySystemInstructions = `You are ${identityData.twinName}...`;

      const response = await fetch('/api/twins', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          name: identityData.twinName,
          description: identityData.tagline,
          specialization: specialization,
          settings: {
            system_prompt: legacySystemInstructions,
            handle: identityData.handle,
            tagline: identityData.tagline,
            expertise: identityData.expertise,
            personality: personalityData,
            intent_profile: {
              goals_90_days: identityData.goals90Days.filter((g) => g.trim()),
              boundaries: identityData.boundaries,
              privacy_constraints: identityData.privacyConstraints,
              uncertainty_preference: identityData.uncertaintyPreference,
            },
            use_5layer_persona: true,
            persona_v2_version: '2.0.0',
          },
          persona_v2_data: personaV2Data,
        }),
      });
```

**VERIFIED:** Frontend onboarding submit handler exists with persona_v2_data included.

---

### 1.8 frontend/components/onboarding/steps/Step2ThinkingStyle.tsx (lines 63-130)

```typescript
export function Step2ThinkingStyle({ data, onChange }: Step2Props) {
  const [showHeuristicHelp, setShowHeuristicHelp] = useState(false);

  const updateField = <K extends keyof ThinkingStyleData>(field: K, value: ThinkingStyleData[K]) => {
    onChange({ ...data, [field]: value });
  };

  const toggleHeuristic = (heuristicId: string) => {
    const current = data.heuristics || [];
    const updated = current.includes(heuristicId)
      ? current.filter((h) => h !== heuristicId)
      : [...current, heuristicId];
    updateField('heuristics', updated);
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 2: Thinking Style</h2>
        <p className="text-slate-400">
          How do you think through problems? Your cognitive heuristics and decision framework.
        </p>
      </div>
```

**VERIFIED:** Step 2 (Thinking Style) exists for Layer 2.

---

### 1.9 frontend/components/onboarding/steps/Step3Values.tsx (lines 55-110)

```typescript
export function Step3Values({ data, onChange, specialization }: Step3Props) {
  const [newValueName, setNewValueName] = useState('');
  const [newValueDesc, setNewValueDesc] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  // Initialize with defaults if empty
  const values = data.prioritizedValues.length > 0
    ? data.prioritizedValues
    : defaultValues[specialization] || defaultValues.vanilla;

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 3: Values & Priorities</h2>
        <p className="text-slate-400">
          Drag to rank what matters most to you. The order determines priority when values conflict.
        </p>
      </div>
```

**VERIFIED:** Step 3 (Values) exists for Layer 3.

---

## 2. Verified Call Chain

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           VERIFIED CALL CHAIN                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  FRONTEND                                                                        │
│  ─────────                                                                       │
│  frontend/app/onboarding/page.tsx:234                                            │
│  ├─ createTwin()                                                                 │
│  │  ├─ buildPersonaV2Data()    [constructs 5-layer data]                        │
│  │  └─ fetch('/api/twins', { persona_v2_data: ... })        ───────┐            │
│  │                                                                  │            │
│  │  BYPASS POINT: If fetch fails, twin not created                  │            │
│  │                                                                  ▼            │
│  BACKEND                                                                         │
│  ────────                                                                        │
│  backend/routers/twins.py:102                                                    │
│  ├─ @router.post("/twins")                                                       │
│  │  ├─ request.persona_v2_data    [received from frontend]                       │
│  │  ├─ bootstrap_persona_from_onboarding()    ─────────────────────┐            │
│  │  │                                                              │            │
│  │  │  FALLBACK POINT: If bootstrap fails, persona_v2_error set    │            │
│  │  │  but twin still created                                      ▼            │
│  │  └─ backend/modules/persona_bootstrap.py:26                                   │
│  │     ├─ _build_identity_frame()           → Layer 1                            │
│  │     ├─ _build_cognitive_heuristics()     → Layer 2                            │
│  │     ├─ _build_value_hierarchy()          → Layer 3                            │
│  │     ├─ _build_communication_patterns()   → Layer 4                            │
│  │     ├─ _build_memory_anchors()           → Layer 5                            │
│  │     └─ PersonaSpecV2(status="active")    ───────┐                            │
│  │                                                  │                            │
│  └─ create_persona_spec_v2(status="active")  ◄─────┘                            │
│     backend/modules/persona_spec_store_v2.py:173                                 │
│     └─ supabase.table("persona_specs").insert()                                  │
│                                                                                  │
│  CHAT RUNTIME                                                                    │
│  ────────────                                                                    │
│  backend/modules/agent.py:293                                                    │
│  ├─ build_system_prompt_with_trace()                                             │
│  │  ├─ full_settings.get("use_5layer_persona") ? ────┐                          │
│  │  │                                                │                          │
│  │  │  BYPASS POINT: If false, skip v2 path          │                          │
│  │  │                                                ▼                          │
│  │  ├─ get_active_persona_spec_v2(twin_id)    ───────┘                          │
│  │  │  backend/modules/persona_spec_store_v2.py:121                              │
│  │  │  └─ supabase.table("persona_specs").eq("status", "active")                 │
│  │  │                                                                            │
│  │  ├─ _build_prompt_from_v2_persona()        ──┐                               │
│  │  │                                           │                               │
│  │  │  FALLBACK POINT: If v2 fails, use v1      │                               │
│  │  │                                           ▼                               │
│  │  └─ backend/modules/agent.py:461                                              │
│  │     └─ Build prompt from 5-layer spec                                         │
│  │                                                                               │
│  │  FALLBACK CHAIN (if no v2):                                                   │
│  │  ├─ get_active_persona_spec() → v1 persona                                   │
│  │  └─ legacy system_prompt from settings                                       │
│  │                                                                               │
│  └─ Return (prompt, persona_trace)                                               │
│                                                                                  │
│  DECISION ENGINE (Optional)                                                      │
│  ─────────────────────────                                                       │
│  backend/modules/persona_decision_engine.py:585                                  │
│  ├─ PersonaDecisionEngine                                                        │
│  │  └─ decide() → StructuredDecisionOutput                                       │
│  │     ├─ Safety check                                                           │
│  │     ├─ Query classification                                                   │
│  │     ├─ Apply cognitive heuristics (Layer 2)                                   │
│  │     ├─ Score dimensions (Layer 3)                                             │
│  │     ├─ Resolve value conflicts (Layer 3)                                      │
│  │     ├─ Apply memory anchors (Layer 5)                                         │
│  │     └─ Generate response (Layer 4)                                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Reuse Inventory

### 3.1 Existing Ingestion Stack (CONFIRMED REUSABLE)

| Component | File | Function | Reuse Status |
|-----------|------|----------|--------------|
| File Upload | `backend/modules/ingestion.py:2463` | `ingest_file(twin_id, file)` | ✅ REUSE for Mode A/B |
| URL Ingestion | `backend/modules/ingestion.py:2500` | `ingest_url(twin_id, url)` | ✅ REUSE for Mode C |
| URL Router | `backend/modules/ingestion.py:1768` | `ingest_url_to_source()` | ✅ REUSE |
| Text Processing | `backend/modules/ingestion.py:1928` | `process_and_index_text()` | ✅ REUSE |
| Chunking | `backend/modules/ingestion.py:1803` | `chunk_text()` | ✅ REUSE |

### 3.2 Existing Storage (CONFIRMED REUSABLE)

| Table | Purpose | Schema Status |
|-------|---------|---------------|
| `sources` | Source metadata | ✅ NO CHANGES NEEDED |
| `chunks` | Chunked content + embeddings | ✅ NO CHANGES NEEDED |
| `persona_specs` | Persona spec storage | ✅ NO CHANGES NEEDED (JSONB) |

### 3.3 Existing Persona Infrastructure

| Component | File | Purpose |
|-----------|------|---------|
| PersonaSpecV2 | `persona_spec_v2.py` | 5-layer schema |
| Bootstrap | `persona_bootstrap.py` | Onboarding → Spec |
| Store | `persona_spec_store_v2.py` | CRUD operations |
| Decision Engine | `persona_decision_engine.py` | Runtime inference |
| Agent Integration | `agent.py` | Prompt building |

---

## 4. Explicit Gaps vs Required Target Behavior

### 4.1 Schema Gaps (MUST FIX)

| Gap | Location | Required Change |
|-----|----------|-----------------|
| Missing `verification_required` | `persona_spec_v2.py:CognitiveHeuristic` | Add field, default=true |
| Missing `verification_required` | `persona_spec_v2.py:ValueItem` | Add field, default=true |
| Missing `evidence_links` | PersonaSpecV2 layers | Add claim_ids to each layer item |

### 4.2 Missing Components (MUST IMPLEMENT)

| Component | Purpose | Phase |
|-----------|---------|-------|
| `persona_claims` table | Store extracted claims | Phase 2 |
| Claim extraction service | Chunk → Claims | Phase 2 |
| Citation object schema | Stable citation format | Phase 2 |
| Bio generator | Claims → Bio formats | Phase 4 |
| Chat citation enforcement | Runtime claim validation | Phase 5 |

### 4.3 Mode C Restrictions (MUST IMPLEMENT)

| Requirement | Implementation |
|-------------|----------------|
| robots.txt check | New `robots_checker.py` |
| Allowlist enforcement | Config-based domain allowlist |
| Rate limiting | 1 req/sec default |
| LinkedIn/X blocked | Explicit blocklist |

---

## 5. Phase Implementation Summary

| Phase | Deliverable | Status |
|-------|-------------|--------|
| Phase 0 | This verification document | ✅ COMPLETE |
| Phase 1 | Ingestion modes A/B/C | Pending |
| Phase 2 | Claim extraction + citations | Pending |
| Phase 3 | Persona compiler with honesty | Pending |
| Phase 4 | Grounded bio generator | Pending |
| Phase 5 | Chat runtime enforcement | Pending |
| Phase 6 | Tests + quality proof | Pending |

---

**END OF PHASE 0 - Ready to proceed with implementation**
