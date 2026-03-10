# Link-First Persona - Architectural Alignment Specification

**Date:** 2026-02-20  
**Status:** SPECIFICATION  
**Author:** Kimi2 (Principal Engineer)

---

## EXECUTIVE SUMMARY

This document specifies the architectural alignment required to integrate Link-First Persona with the existing onboarding and twin creation flow. This is NOT feature expansion but state machine enforcement and architectural alignment.

**Key Constraints:**
- Legacy twins: ZERO breaking changes
- Manual onboarding: Works exactly as before
- Link-First: New state machine path only
- Feature flag: LINK_FIRST_ENABLED controls availability

---

## PHASE A — Backend Audit & Refactor

### A.1 Database Schema Changes

#### Migration File: `backend/migrations/20260220_add_twin_status.sql`

```sql
-- Add status field to twins table
ALTER TABLE twins ADD COLUMN IF NOT EXISTS status VARCHAR(20) 
  DEFAULT 'active' 
  CHECK (status IN ('draft', 'ingesting', 'claims_ready', 'clarification_pending', 'persona_built', 'active', 'archived'));

-- Add mode field to distinguish creation paths
ALTER TABLE twins ADD COLUMN IF NOT EXISTS creation_mode VARCHAR(20) 
  DEFAULT 'manual' 
  CHECK (creation_mode IN ('manual', 'link_first'));

-- Add feature flag check (for application-level control)
COMMENT ON COLUMN twins.status IS 'Twin lifecycle state: draft->ingesting->claims_ready->clarification_pending->persona_built->active';
COMMENT ON COLUMN twins.creation_mode IS 'Creation path: manual (onboarding_v2) or link_first';

-- Index for status queries
CREATE INDEX IF NOT EXISTS idx_twins_status ON twins(status);
CREATE INDEX IF NOT EXISTS idx_twins_creation_mode ON twins(creation_mode);

-- Update existing twins to have status='active', creation_mode='manual'
UPDATE twins SET status = 'active', creation_mode = 'manual' WHERE status IS NULL;
```

**Verification:**
```bash
psql $DATABASE_URL -c "\d twins" | grep -E "status|creation_mode"
```

---

### A.2 Modify POST /twins

#### File: `backend/routers/twins.py`

**Current State (lines 68-76):**
```python
class TwinCreateRequest(BaseModel):
    name: str
    tenant_id: Optional[str] = None  # IGNORED: server always resolves tenant_id
    description: Optional[str] = None
    specialization: str = "vanilla"
    settings: Optional[Dict[str, Any]] = None
    # NEW: Structured 5-Layer Persona data from onboarding
    persona_v2_data: Optional[Dict[str, Any]] = None
```

**DIFF - Add creation_mode field:**
```python
class TwinCreateRequest(BaseModel):
    name: str
    tenant_id: Optional[str] = None  # IGNORED: server always resolves tenant_id
    description: Optional[str] = None
    specialization: str = "vanilla"
    settings: Optional[Dict[str, Any]] = None
    # NEW: Structured 5-Layer Persona data from onboarding
    persona_v2_data: Optional[Dict[str, Any]] = None
    # NEW: Creation mode for Link-First architecture
    creation_mode: str = "manual"  # "manual" | "link_first"
```

**Current State (lines 158-176):**
```python
        # ====================================================================
        # STEP 1: Create the twin with 5-Layer Persona enabled
        # ====================================================================
        
        # Enhanced settings with 5-Layer Persona configuration
        settings = request.settings or {}
        settings["use_5layer_persona"] = True  # NEW: Always true for new twins
        settings["persona_v2_version"] = "2.0.0"  # NEW: Track persona version
        
        data = {
            "name": requested_name,
            "tenant_id": tenant_id,
            "creator_id": (derive_creator_ids(user) or [f"tenant_{tenant_id}"])[0],
            "description": request.description or f"{requested_name}'s digital twin",
            "specialization": request.specialization,
            "settings": settings
        }
```

**DIFF - Add state machine logic:**
```python
        # ====================================================================
        # STEP 1: Create the twin with state machine initialization
        # ====================================================================
        
        # Determine creation path and initial state
        creation_mode = request.creation_mode or "manual"
        is_link_first = creation_mode == "link_first"
        
        # Feature flag check for link_first
        link_first_enabled = os.getenv("LINK_FIRST_ENABLED", "false").lower() == "true"
        if is_link_first and not link_first_enabled:
            raise HTTPException(
                status_code=400, 
                detail="Link-First Persona is not enabled. Use creation_mode='manual' or contact admin."
            )
        
        # Set initial status based on creation mode
        initial_status = "draft" if is_link_first else "active"
        
        # Enhanced settings with 5-Layer Persona configuration
        settings = request.settings or {}
        settings["use_5layer_persona"] = True
        settings["persona_v2_version"] = "2.0.0"
        settings["creation_mode"] = creation_mode  # Store in settings for redundancy
        
        data = {
            "name": requested_name,
            "tenant_id": tenant_id,
            "creator_id": (derive_creator_ids(user) or [f"tenant_{tenant_id}"])[0],
            "description": request.description or f"{requested_name}'s digital twin",
            "specialization": request.specialization,
            "settings": settings,
            "status": initial_status,  # NEW: State machine initialization
            "creation_mode": creation_mode,  # NEW: Creation path tracking
        }
```

**Current State (lines 198-239):**
```python
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

**DIFF - Conditionally skip bootstrap for link_first:**
```python
            # ====================================================================
            # STEP 2: Conditionally create persona based on creation mode
            # ====================================================================
            
            if is_link_first:
                # Link-First path: Do NOT bootstrap persona
                # Persona will be built from claims after ingestion
                print(f"[TWINS] Link-First twin created in draft state: {twin_id}")
                twin["persona_v2"] = {
                    "status": "pending_claims",
                    "message": "Upload content to build persona from claims",
                }
            else:
                # Manual path: Bootstrap persona from onboarding data
                try:
                    onboarding_data = request.persona_v2_data or {}
                    onboarding_data["twin_name"] = requested_name
                    onboarding_data["specialization"] = request.specialization
                    
                    persona_spec = bootstrap_persona_from_onboarding(onboarding_data)
                    
                    persona_record = create_persona_spec_v2(
                        twin_id=twin_id,
                        tenant_id=tenant_id,
                        created_by=user_id,
                        spec=persona_spec.model_dump(mode="json"),
                        status="active",
                        source="onboarding_v2",  # Explicit source tracking
                        metadata={
                            "onboarding_version": "2.0",
                            "specialization": request.specialization,
                            "auto_published": True,
                            "creation_mode": "manual",
                        }
                    )
                    
                    print(f"[TWINS] 5-Layer Persona Spec v2 created: {persona_record.get('id')}")
                    
                    twin["persona_v2"] = {
                        "id": persona_record.get("id"),
                        "version": "2.0.0",
                        "status": "active",
                        "auto_created": True,
                    }
                    
                except Exception as persona_error:
                    print(f"[TWINS] WARNING: Failed to auto-create persona: {persona_error}")
                    twin["persona_v2_error"] = str(persona_error)
```

**Current State (lines 241-254):**
```python
            # ====================================================================
            # STEP 3: Auto-Create Default Group
            # ====================================================================
            
            try:
                await create_group(
                    twin_id=twin_id,
                    name="Default Group",
                    description="Standard access group for all content",
                    is_default=True
                )
                print(f"[TWINS] Default group created for twin: {twin_id}")
            except Exception as ge:
                print(f"[TWINS] WARNING: Failed to create default group: {ge}")
```

**DIFF - Skip group creation for link_first in draft:**
```python
            # ====================================================================
            # STEP 3: Auto-Create Default Group (only for manual mode)
            # ====================================================================
            
            if not is_link_first:
                # Only create groups for manual twins (link_first will create after ingestion)
                try:
                    await create_group(
                        twin_id=twin_id,
                        name="Default Group",
                        description="Standard access group for all content",
                        is_default=True
                    )
                    print(f"[TWINS] Default group created for twin: {twin_id}")
                except Exception as ge:
                    print(f"[TWINS] WARNING: Failed to create default group: {ge}")
```

---

### A.3 Modify agent.py Chat Blocking

#### File: `backend/modules/agent.py`

**Add at top of file (after imports):**
```python
# =============================================================================
# Link-First State Machine Constants
# =============================================================================

CHAT_BLOCKED_STATUS_MESSAGES = {
    "draft": "This twin is in draft mode. Complete the Link-First setup to enable chat.",
    "ingesting": "Processing your content. Chat will be available once ingestion completes.",
    "claims_ready": "Review extracted claims before enabling chat.",
    "clarification_pending": "Answer clarification questions to complete your persona.",
    "persona_built": "Persona is being finalized. Chat will be available shortly.",
}

LINK_FIRST_CITATION_RULES = """
CITATION RULES (Link-First Persona):
1. Every owner-specific factual claim MUST cite [claim_id]
2. If no claim supports a statement, ask a clarification question
3. Do NOT make assumptions beyond the documented claims
4. Uncertainty is preferred to unsupported assertions

CITATION FORMAT: 'I prefer B2B investments [claim_abc123]'
"""
```

**Modify _build_prompt_from_v2_persona (existing modifications):**

**Current State (from previous implementation):**
```python
def _build_prompt_from_v2_persona(spec: Dict[str, Any], twin_name: str) -> str:
    # ... existing code ...
    
    if is_link_first:
        prompt_parts.extend([
            "",
            "CITATION RULES (Link-First Persona):",
            "1. Every owner-specific factual claim MUST cite [claim_id]",
            "2. If no claim supports a statement, ask a clarification question",
            "3. Do NOT make assumptions beyond the documented claims",
        ])
```

**DIFF - Enhanced with source distinction:**
```python
def _build_prompt_from_v2_persona(spec: Dict[str, Any], twin_name: str, persona_source: str = "") -> str:
    """
    Build system prompt text from 5-Layer Persona Spec v2.
    
    Args:
        spec: Persona spec dict
        twin_name: Name of twin
        persona_source: Source of persona ("onboarding_v2" | "link_first" | "")
    """
    identity = spec.get("identity_frame", {})
    cognitive = spec.get("cognitive_heuristics", {})
    values = spec.get("value_hierarchy", {})
    communication = spec.get("communication_patterns", {})
    
    # Explicit source detection
    is_link_first = (
        persona_source == "link_first" or 
        spec.get("source") == "link_first" or
        spec.get("source") == "link-compile"
    )
    is_onboarding_v2 = (
        persona_source == "onboarding_v2" or
        spec.get("source") == "onboarding_v2" or
        spec.get("source") == "onboarding"
    )
    
    # Layer 1-4 building (existing code)
    # ... (keep existing prompt building) ...
    
    # Add source-specific rules
    if is_link_first:
        prompt_parts.extend([
            "",
            "=" * 60,
            "LINK-FIRST PERSONA ENFORCEMENT",
            "=" * 60,
            "",
            "This persona was built from verified claims.",
            "",
            "CITATION RULES:",
            "- Every owner-specific factual claim MUST cite [claim_id]",
            "- Example: 'I prefer B2B over B2C [claim_abc123]'",
            "",
            "VERIFICATION RULES:",
            "- If no claim supports a statement → Ask clarification",
            "- If claim confidence < 0.6 → Express uncertainty",
            "- Never invent preferences or experiences",
            "",
        ])
        
        # Add Layer 2/3 verification requirements
        verification_required_heuristics = [
            h for h in cognitive.get("heuristics", [])
            if h.get("verification_required", True)
        ]
        if verification_required_heuristics:
            prompt_parts.extend([
                "HEURISTICS REQUIRING VERIFICATION:",
            ])
            for h in verification_required_heuristics[:3]:
                prompt_parts.append(f"- {h.get('name', 'Unnamed')}")
            prompt_parts.append("")
    
    elif is_onboarding_v2:
        prompt_parts.extend([
            "",
            "=" * 60,
            "MANUAL PERSONA (Onboarding v2)",
            "=" * 60,
            "",
            "This persona was built from manual onboarding.",
            "Standard citation rules apply.",
            "",
        ])
    
    return "\n".join(prompt_parts)
```

---

### A.4 Modify chat.py Router

#### File: `backend/routers/chat.py`

**Add import at top:**
```python
from modules.link_first_guard import check_twin_chat_allowed, ChatBlockedError
```

**Find the main chat endpoint (likely around line 200+):**

**Add before run_agent_stream call:**
```python
@router.post("/chat/{twin_id}")
async def chat_with_twin(
    twin_id: str,
    request: ChatRequest,
    user=Depends(get_current_user),
):
    """Main chat endpoint with Link-First state enforcement."""
    
    # Fetch twin status
    twin_res = supabase.table("twins").select("status, creation_mode").eq("id", twin_id).single().execute()
    
    if not twin_res.data:
        raise HTTPException(404, "Twin not found")
    
    twin = twin_res.data
    twin_status = twin.get("status", "active")
    creation_mode = twin.get("creation_mode", "manual")
    
    # Block chat if twin not in active state
    if twin_status != "active":
        from modules.agent import CHAT_BLOCKED_STATUS_MESSAGES
        
        block_message = CHAT_BLOCKED_STATUS_MESSAGES.get(
            twin_status, 
            f"Twin is in {twin_status} state. Chat not available."
        )
        
        return {
            "response": block_message,
            "blocked": True,
            "status": twin_status,
            "next_step": _get_next_step_for_status(twin_status, creation_mode),
        }
    
    # Continue with existing chat logic
    # ... (rest of existing chat handler)
```

**Add helper function:**
```python
def _get_next_step_for_status(status: str, creation_mode: str) -> str:
    """Return the next step URL or action for the user."""
    if creation_mode == "link_first":
        status_to_step = {
            "draft": "/onboarding/link-first/upload",
            "ingesting": "/onboarding/link-first/progress",
            "claims_ready": "/onboarding/link-first/review",
            "clarification_pending": "/onboarding/link-first/clarify",
            "persona_built": "/onboarding/link-first/preview",
        }
        return status_to_step.get(status, "/onboarding")
    return "/onboarding"
```

---

## PHASE B — Frontend Alignment

### B.1 Modify onboarding/page.tsx

#### File: `frontend/app/onboarding/page.tsx`

**Current State (lines 1-14):**
```typescript
'use client';

import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { StepIndicator } from '@/components/onboarding/StepIndicator';
import { Step1Identity, IdentityFormData } from '@/components/onboarding/steps/Step1Identity';
import { Step2ThinkingStyle } from '@/components/onboarding/steps/Step2ThinkingStyle';
import { Step3Values } from '@/components/onboarding/steps/Step3Values';
import { Step4Communication } from '@/components/onboarding/steps/Step4Communication';
import { Step5Memory } from '@/components/onboarding/steps/Step5Memory';
import { Step6Review } from '@/components/onboarding/steps/Step6Review';
import { getSupabaseClient } from '@/lib/supabase/client';
```

**DIFF - Add imports and mode state:**
```typescript
'use client';

import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { StepIndicator } from '@/components/onboarding/StepIndicator';
import { Step1Identity, IdentityFormData } from '@/components/onboarding/steps/Step1Identity';
import { Step2ThinkingStyle } from '@/components/onboarding/steps/Step2ThinkingStyle';
import { Step3Values } from '@/components/onboarding/steps/Step3Values';
import { Step4Communication } from '@/components/onboarding/steps/Step4Communication';
import { Step5Memory } from '@/components/onboarding/steps/Step5Memory';
import { Step6Review } from '@/components/onboarding/steps/Step6Review';

// Link-First Components
import { StepModeSelect } from '@/components/onboarding/steps/StepModeSelect';
import { StepLinkSubmission } from '@/components/onboarding/steps/StepLinkSubmission';
import { StepIngestionProgress } from '@/components/onboarding/steps/StepIngestionProgress';
import { StepClaimReview } from '@/components/onboarding/steps/StepClaimReview';
import { StepClarification } from '@/components/onboarding/steps/StepClarification';
import { StepPersonaPreview } from '@/components/onboarding/steps/StepPersonaPreview';

import { getSupabaseClient } from '@/lib/supabase/client';

// Feature flag
const LINK_FIRST_ENABLED = process.env.NEXT_PUBLIC_LINK_FIRST_ENABLED === 'true';

// Mode type
type CreationMode = 'manual' | 'link_first' | null;
```

**Add state variables (after line 106):**
```typescript
function OnboardingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get('returnTo');

  const [currentStep, setCurrentStep] = useState(1);
  const [isLaunching, setIsLaunching] = useState(false);
  
  // NEW: Mode selection state
  const [creationMode, setCreationMode] = useState<CreationMode>(null);
  const [twinId, setTwinId] = useState<string | null>(null);
  const [twinStatus, setTwinStatus] = useState<string>('draft');
```

**Add mode-specific step configuration (replace lines 50-59):**
```typescript
// Step Configuration - varies by mode
const MANUAL_STEPS = ['Identity', 'Thinking Style', 'Values', 'Communication', 'Memory', 'Review'];
const LINK_FIRST_STEPS = ['Mode Select', 'Submit Links', 'Processing', 'Review Claims', 'Clarify', 'Preview'];

const getStepTitles = (mode: CreationMode) => {
  if (mode === 'link_first') return LINK_FIRST_STEPS;
  return MANUAL_STEPS;
};

const getTotalSteps = (mode: CreationMode) => {
  return getStepTitles(mode).length;
};
```

**Add mode selection render (modify renderStep function around line 317):**
```typescript
  const renderStep = () => {
    // Step 0: Mode Selection (only if feature enabled)
    if (currentStep === 1 && LINK_FIRST_ENABLED && !creationMode) {
      return (
        <StepModeSelect
          onSelect={(mode) => {
            setCreationMode(mode);
            // If link_first, create twin in draft state immediately
            if (mode === 'link_first') {
              createTwinDraft();
            }
          }}
        />
      );
    }

    // Manual mode: Steps 1-6 (existing)
    if (creationMode === 'manual' || !LINK_FIRST_ENABLED) {
      switch (currentStep) {
        case 1:
          return <Step1Identity data={identityData} onChange={setIdentityData} onSpecializationChange={setSpecialization} />;
        case 2:
          return <Step2ThinkingStyle data={thinkingData} onChange={setThinkingData} />;
        case 3:
          return <Step3Values data={valuesData} onChange={setValuesData} specialization={specialization} />;
        case 4:
          return <Step4Communication personality={personalityData} onPersonalityChange={setPersonalityData} />;
        case 5:
          return <Step5Memory data={memoryData} onChange={setMemoryData} />;
        case 6:
          return (
            <Step6Review
              data={{...}}
              onLaunch={createTwin}
              isLaunching={isLaunching}
            />
          );
        default:
          return null;
      }
    }

    // Link-First mode: New flow
    if (creationMode === 'link_first') {
      switch (currentStep) {
        case 1: // Mode already selected, go to submission
          return (
            <StepLinkSubmission
              twinId={twinId}
              onSubmit={handleLinkSubmission}
              onStatusChange={setTwinStatus}
            />
          );
        case 2: // Ingestion Progress
          return (
            <StepIngestionProgress
              twinId={twinId}
              onComplete={() => setCurrentStep(3)}
            />
          );
        case 3: // Claim Review
          return (
            <StepClaimReview
              twinId={twinId}
              onApprove={() => setCurrentStep(4)}
            />
          );
        case 4: // Clarification
          return (
            <StepClarification
              twinId={twinId}
              onComplete={() => setCurrentStep(5)}
            />
          );
        case 5: // Preview
          return (
            <StepPersonaPreview
              twinId={twinId}
              onActivate={activateTwin}
            />
          );
        default:
          return null;
      }
    }
  };
```

**Add new functions (before renderStep):**
```typescript
  const createTwinDraft = async () => {
    // Create twin in draft state for link_first
    const response = await fetch('/api/twins', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Draft Twin', // Will be updated later
        creation_mode: 'link_first',
        settings: { use_5layer_persona: true },
      }),
    });
    
    const twin = await response.json();
    setTwinId(twin.id);
  };

  const handleLinkSubmission = async (urls: string[], files: File[]) => {
    // Start ingestion job
    const response = await fetch(`/api/persona/link-compile/jobs/mode-c`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ twin_id: twinId, urls }),
    });
    
    setCurrentStep(2); // Move to progress
  };

  const activateTwin = async () => {
    // Finalize twin and set status to active
    const response = await fetch(`/api/twins/${twinId}/activate`, {
      method: 'POST',
    });
    
    router.push(`/twins/${twinId}`);
  };
```

---

### B.2 Create New Components

#### File: `frontend/components/onboarding/steps/StepModeSelect.tsx`

```typescript
'use client';

import { Card } from '@/components/ui/Card';

interface StepModeSelectProps {
  onSelect: (mode: 'manual' | 'link_first') => void;
}

export function StepModeSelect({ onSelect }: StepModeSelectProps) {
  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Choose Your Path</h2>
        <p className="text-slate-400">
          How would you like to build your Digital Twin?
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Manual Mode */}
        <Card 
          className="p-6 cursor-pointer hover:border-indigo-500 transition-colors"
          onClick={() => onSelect('manual')}
        >
          <div className="text-center">
            <span className="text-4xl mb-4 block">✍️</span>
            <h3 className="text-xl font-semibold mb-2">Manual Setup</h3>
            <p className="text-slate-400 text-sm">
              Answer questions about your identity, thinking style, values, and communication preferences.
            </p>
            <ul className="text-left text-sm text-slate-300 mt-4 space-y-1">
              <li>✓ 6-step guided questionnaire</li>
              <li>✓ Immediate chat access</li>
              <li>✓ Best for clear self-knowledge</li>
            </ul>
          </div>
        </Card>

        {/* Link-First Mode */}
        <Card 
          className="p-6 cursor-pointer hover:border-indigo-500 transition-colors"
          onClick={() => onSelect('link_first')}
        >
          <div className="text-center">
            <span className="text-4xl mb-4 block">🔗</span>
            <h3 className="text-xl font-semibold mb-2">Link-First (Beta)</h3>
            <p className="text-slate-400 text-sm">
              Import content from your writing, exports, and public profiles.
            </p>
            <ul className="text-left text-sm text-slate-300 mt-4 space-y-1">
              <li>✓ Import LinkedIn, Twitter, articles</li>
              <li>✓ AI extracts claims from content</li>
              <li>✓ Verified, citable persona</li>
            </ul>
          </div>
        </Card>
      </div>
    </div>
  );
}
```

#### File: `frontend/components/onboarding/steps/StepLinkSubmission.tsx`

```typescript
'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';

interface StepLinkSubmissionProps {
  twinId: string | null;
  onSubmit: (urls: string[], files: File[]) => void;
  onStatusChange: (status: string) => void;
}

export function StepLinkSubmission({ twinId, onSubmit, onStatusChange }: StepLinkSubmissionProps) {
  const [urls, setUrls] = useState<string[]>(['']);
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<'urls' | 'files'>('urls');

  const handleSubmit = () => {
    const validUrls = urls.filter(u => u.trim());
    onSubmit(validUrls, files);
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Submit Your Content</h2>
        <p className="text-slate-400">
          Add links to your writing or upload exports to build your persona.
        </p>
      </div>

      {/* Mode Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setMode('urls')}
          className={`flex-1 py-2 rounded-lg ${mode === 'urls' ? 'bg-indigo-600' : 'bg-slate-800'}`}
        >
          Web Links (Mode C)
        </button>
        <button
          onClick={() => setMode('files')}
          className={`flex-1 py-2 rounded-lg ${mode === 'files' ? 'bg-indigo-600' : 'bg-slate-800'}`}
        >
          File Upload (Mode A/B)
        </button>
      </div>

      {mode === 'urls' ? (
        <Card className="p-6">
          <h3 className="font-semibold mb-4">Public Links</h3>
          <p className="text-sm text-slate-400 mb-4">
            GitHub READMEs, blog posts, articles. LinkedIn and Twitter are blocked for crawling.
          </p>
          {urls.map((url, idx) => (
            <input
              key={idx}
              type="url"
              value={url}
              onChange={(e) => {
                const newUrls = [...urls];
                newUrls[idx] = e.target.value;
                setUrls(newUrls);
              }}
              placeholder="https://github.com/username/repo"
              className="w-full mb-3 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg"
            />
          ))}
          <button
            onClick={() => setUrls([...urls, ''])}
            className="text-indigo-400 text-sm"
          >
            + Add another link
          </button>
        </Card>
      ) : (
        <Card className="p-6">
          <h3 className="font-semibold mb-4">File Upload</h3>
          <p className="text-sm text-slate-400 mb-4">
            LinkedIn exports, Twitter archives, PDFs, documents.
          </p>
          <input
            type="file"
            multiple
            accept=".zip,.pdf,.csv,.html"
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
            className="w-full"
          />
        </Card>
      )}

      <button
        onClick={handleSubmit}
        disabled={!twinId}
        className="w-full py-3 bg-indigo-600 rounded-lg font-semibold disabled:opacity-50"
      >
        Start Processing
      </button>
    </div>
  );
}
```

(Additional components: StepIngestionProgress, StepClaimReview, StepClarification, StepPersonaPreview follow similar patterns with state-based rendering)

---

## PHASE C — End-to-End State Machine

### State Transition Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LINK-FIRST STATE MACHINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   MANUAL MODE                          LINK-FIRST MODE                       │
│   ───────────                          ───────────────                       │
│                                                                              │
│   POST /twins                          POST /twins                           │
│   (creation_mode=manual)               (creation_mode=link_first)            │
│        │                                    │                                │
│        ▼                                    ▼                                │
│   ┌─────────┐                         ┌─────────┐                           │
│   │  ACTIVE │                         │  DRAFT  │ ◄── Can edit name         │
│   └────┬────┘                         └────┬────┘                           │
│        │                                    │                                │
│        │ Chat enabled                       │ Submit links                   │
│        │                                    ▼                                │
│        │                               ┌──────────┐                         │
│        │                               │INGESTING │ ◄── Processing          │
│        │                               └────┬─────┘                         │
│        │                                    │ Extraction complete           │
│        │                                    ▼                                │
│        │                               ┌───────────┐                        │
│        │                               │CLAIMS_    │ ◄── Review claims     │
│        │                               │  READY    │    (owner approves)    │
│        │                               └────┬──────┘                        │
│        │                                    │ Low confidence claims         │
│        │                                    ▼                                │
│        │                               ┌────────────────┐                   │
│        │                               │CLARIFICATION_  │ ◄── Q&A          │
│        │                               │   PENDING      │                   │
│        │                               └────┬───────────┘                   │
│        │                                    │ All answered                  │
│        │                                    ▼                                │
│        │                               ┌────────────┐                       │
│        │                               │PERSONA_    │ ◄── Preview          │
│        │                               │  BUILT     │    generated bio      │
│        │                               └────┬───────┘                       │
│        │                                    │ Activate                      │
│        │                                    ▼                                │
│        └──────────────────────────────►┌─────────┐                          │
│                                        │  ACTIVE │ ◄── Chat enabled        │
│                                        └─────────┘                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### State-to-Frontend Mapping

| Backend State | Frontend Screen | User Action |
|---------------|-----------------|-------------|
| `draft` | StepModeSelect → StepLinkSubmission | Submit content links/files |
| `ingesting` | StepIngestionProgress | Wait for processing |
| `claims_ready` | StepClaimReview | Approve/reject extracted claims |
| `clarification_pending` | StepClarification | Answer questions |
| `persona_built` | StepPersonaPreview | Preview and activate |
| `active` | Twin Chat | Full chat access |

### State Transition API

```typescript
// Backend endpoints for state transitions

// Triggered by: File upload complete
POST /api/twins/{id}/transition/ingesting
→ Sets status: ingesting
→ Starts claim extraction job

// Triggered by: Extraction complete
POST /api/twins/{id}/transition/claims-ready
→ Sets status: claims_ready
→ Returns extracted claims

// Triggered by: Claims approved
POST /api/twins/{id}/transition/clarification
→ Sets status: clarification_pending
→ Generates clarification questions

// Triggered by: Clarifications complete
POST /api/twins/{id}/transition/persona-built
→ Sets status: persona_built
→ Compiles PersonaSpecV2
→ Generates bio variants

// Triggered by: User activates
POST /api/twins/{id}/activate
→ Sets status: active
→ Enables chat
```

---

## PHASE D — Migration Safety

### D.1 Legacy Twin Compatibility

**Checklist:**
- [ ] Existing twins have `status='active'` (migration sets default)
- [ ] Existing twins have `creation_mode='manual'` (migration sets default)
- [ ] Chat continues to work for `status='active'` twins
- [ ] No change to manual onboarding flow when `creation_mode='manual'`

**Migration Query:**
```sql
-- Verify all existing twins are unaffected
SELECT 
  id, 
  name, 
  status, 
  creation_mode,
  settings->>'use_5layer_persona' as use_v2
FROM twins 
WHERE created_at < '2026-02-20';

-- All should show: status='active', creation_mode='manual'
```

### D.2 Feature Flag

**Environment Variable:**
```bash
# .env
LINK_FIRST_ENABLED=true  # Enable Link-First mode option
```

**Backend Check:**
```python
# backend/routers/twins.py
link_first_enabled = os.getenv("LINK_FIRST_ENABLED", "false").lower() == "true"
if is_link_first and not link_first_enabled:
    raise HTTPException(400, "Link-First not enabled")
```

**Frontend Check:**
```typescript
// frontend/app/onboarding/page.tsx
const LINK_FIRST_ENABLED = process.env.NEXT_PUBLIC_LINK_FIRST_ENABLED === 'true';

// Only show mode selector if enabled
{LINK_FIRST_ENABLED && <StepModeSelect ... />}
```

### D.3 Rollback Plan

```sql
-- Emergency rollback: Disable link-first twins
UPDATE twins SET status = 'archived' 
WHERE creation_mode = 'link_first' AND status != 'active';

-- Remove status columns (revert migration)
ALTER TABLE twins DROP COLUMN IF EXISTS status;
ALTER TABLE twins DROP COLUMN IF EXISTS creation_mode;
```

---

## Deliverables Checklist

### 1. Updated Onboarding UX Spec
- [x] Mode selection screen (StepModeSelect)
- [x] Link submission screen (StepLinkSubmission)
- [x] Ingestion progress (StepIngestionProgress)
- [x] Claim review (StepClaimReview)
- [x] Clarification (StepClarification)
- [x] Preview (StepPersonaPreview)

### 2. Backend File-by-File Diff Plan
- [x] `backend/migrations/20260220_add_twin_status.sql`
- [x] `backend/routers/twins.py` (lines 68-76, 158-176, 198-239, 241-254)
- [x] `backend/modules/agent.py` (citation rules, source distinction)
- [x] `backend/routers/chat.py` (status blocking)

### 3. Updated API Contract
- [x] POST /twins accepts `creation_mode`
- [x] Returns twin with `status` field
- [x] Chat blocked unless `status='active'`

### 4. State Transition Diagram
- [x] Visual state machine
- [x] Frontend-to-backend mapping
- [x] Transition API endpoints

### 5. Runtime Selection Verification
- [x] Manual mode: No changes, immediate active
- [x] Link-First: Draft → ... → Active flow
- [x] Feature flag control
- [x] Legacy twin compatibility

---

**END OF SPECIFICATION**
