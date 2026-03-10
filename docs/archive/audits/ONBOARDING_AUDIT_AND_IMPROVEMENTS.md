# Onboarding Audit & 5-Layer Persona Integration Report

**Date:** February 21, 2026  
**Auditor:** System Analysis  
**Status:** ⚠️ Critical Gap Identified

---

## Executive Summary

The current onboarding flow **completely bypasses** the 5-Layer Persona Model we just built. While users provide rich persona data during onboarding, it's converted to a simple text string instead of a structured v2 persona spec.

### The Problem

```
User Input (Rich Structured Data)
    ↓
Onboarding Form (Step1Identity.tsx)
    ↓
Flattened to Text String
    ↓
stored in twins.settings.system_prompt
    ↓
5-Layer Persona Engine NEVER USED ❌
```

### The Opportunity

```
User Input (Rich Structured Data)
    ↓
Onboarding Form (Enhanced)
    ↓
5-Layer Persona Spec (v2.0.0)
    ↓
Structured Decision Engine
    ↓
Consistent, Scored, Explainable Responses ✅
```

---

## Current Onboarding Analysis

### Step 1: Identity (What's Collected)

| Field | Current Use | 5-Layer Mapping | Utilized? |
|-------|-------------|-----------------|-----------|
| `twinName` | system_prompt text | Layer 1: Identity | ❌ No |
| `tagline` | system_prompt text | Layer 1: Identity | ❌ No |
| `specialization` | twin.specialization | Layer 1: Expertise | ❌ No |
| `selectedDomains` | system_prompt text | Layer 1: Expertise | ❌ No |
| `customExpertise` | system_prompt text | Layer 1: Expertise | ❌ No |
| `personality.tone` | system_prompt text | Layer 4: Communication | ❌ No |
| `personality.responseLength` | system_prompt text | Layer 4: Communication | ❌ No |
| `personality.firstPerson` | system_prompt text | Layer 4: Communication | ❌ No |
| `goals90Days` | system_prompt text | Layer 3: Values | ❌ No |
| `boundaries` | system_prompt text | Layer 1: Refusals | ❌ No |
| `privacyConstraints` | system_prompt text | Layer 1: Scope | ❌ No |
| `uncertaintyPreference` | system_prompt text | Layer 2: Heuristics | ❌ No |

### Current Code (Problematic)

```typescript
// frontend/app/onboarding/page.tsx (lines 172-180)
const systemInstructions = `You are ${twinName}${tagline ? `, ${tagline}` : ''}.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personality.tone}, ${personality.responseLength} responses.
${personality.firstPerson ? 'Speak in first person...' : `Refer to yourself as ${twinName}`}
Top goals for next 90 days: ${goals90Days...}
Boundaries: ${boundaries || 'Not set'}
Privacy constraints: ${privacyConstraints || 'Not set'}
Uncertainty preference: ${uncertaintyPreference === 'ask' ? 'Ask...' : 'Infer...'}
${personality.customInstructions ? `Additional: ${personality.customInstructions}` : ''}`;

// Sent to backend
await authFetchStandalone('/twins', {
  method: 'POST',
  body: JSON.stringify({
    name: twinName,
    settings: {
      system_prompt: systemInstructions,  // ← Flat text!
      personality,
      intent_profile: { goals_90_days, boundaries... }
    }
  })
});
```

### Backend Twin Creation (No Persona Integration)

```python
# backend/routers/twins.py (lines 143-150)
data = {
    "name": requested_name,
    "tenant_id": tenant_id,
    "description": request.description,
    "specialization": request.specialization,
    "settings": request.settings,  # ← Just stores JSON, no persona creation
}

# NO persona_spec creation!
# NO 5-Layer bootstrap!
# Persona specs are created separately via /twins/{id}/persona-specs
```

---

## Gap Analysis: What We're Missing

### 1. No Automatic Persona Creation

**Current Flow:**
1. Create twin → stores `system_prompt` text
2. User must manually go to Persona Studio
3. Generate persona spec separately
4. Publish persona spec
5. Only then is 5-Layer Persona active

**Problem:** 99% of users never complete steps 2-5

### 2. Data Loss in Translation

Rich structured data → Flat text → Lost structure

```
Example: "90-day goals"
Input: ["Launch product", "Get 100 customers", "Hire engineer"]
Stored: "Top goals: Launch product; Get 100 customers; Hire engineer"
Lost: Priority order, measurability, timeframes
```

### 3. No Cognitive Framework Setup

Users don't define:
- How they evaluate startups (heuristics)
- What they prioritize (value hierarchy)
- How they make tradeoffs (conflict resolution)

---

## Recommended Solution: Enhanced Onboarding with 5-Layer Persona

### New Onboarding Flow

```
Step 1: Identity Foundation (Layer 1)
├── Name, Handle, Tagline
├── Role Definition
├── Expertise Domains
└── Specialization

Step 2: Thinking Style (Layer 2) ← NEW
├── Reasoning Approach
│   ├── Analytical (data-driven)
│   ├── Intuitive (pattern-based)
│   ├── First Principles (fundamental truths)
│   └── Balanced (adaptive)
├── Evaluation Framework
│   ├── What I look for first
│   ├── Evidence quality criteria
│   └── Confidence thresholds
└── Decision Heuristics

Step 3: Values & Priorities (Layer 3) ← NEW
├── Value Hierarchy (drag to rank)
│   ├── Team quality
│   ├── Market size
│   ├── Traction
│   ├── Defensibility
│   └── Speed
├── Tradeoff Preferences
│   └── "When team quality conflicts with speed..."
└── Scoring Dimensions
    └── Define what 1-5 means for each

Step 4: Communication Style (Layer 4)
├── Tone (existing)
├── Response Length (existing)
├── Signature Phrases ← NEW
│   └── "Here's the thing..."
├── Anti-Patterns ← NEW
│   └── "Never say..."
└── Brevity Preference (existing)

Step 5: Knowledge & Memory (Layer 5) ← NEW
├── Key Experiences
│   └── "What I've learned..."
├── Past Decisions
│   └── "Good calls I've made..."
├── Document Upload (existing)
└── FAQs (existing)

Step 6: Safety & Boundaries ← NEW
├── Topics to Refuse
│   ├── Investment advice
│   ├── Legal advice
│   └── Medical advice
├── Privacy Scope
└── Escalation Triggers

Step 7: Review & Launch
├── Visual Persona Preview
├── Sample Evaluation
└── Launch
```

---

## Implementation Plan

### Phase 1: Backend Changes

#### 1.1 Create Onboarding Persona Bootstrap Endpoint

```python
# backend/routers/twins.py - Add to create_twin

@router.post("/twins")
async def create_twin(request: TwinCreateRequest, user=Depends(get_current_user)):
    # ... existing twin creation code ...
    
    # NEW: Auto-create 5-Layer Persona Spec
    if request.settings and request.settings.get('persona_v2_data'):
        from modules.persona_spec_v2 import PersonaSpecV2, IdentityFrame, CognitiveHeuristics, ValueHierarchy
        from modules.persona_spec_store_v2 import create_persona_spec_v2
        
        v2_data = request.settings['persona_v2_data']
        
        persona_v2 = PersonaSpecV2(
            version="2.0.0",
            name=f"{requested_name} Persona",
            description=v2_data.get('tagline', ''),
            identity_frame=IdentityFrame(
                role_definition=v2_data.get('role_definition', ''),
                expertise_domains=v2_data.get('expertise', []),
                reasoning_style=v2_data.get('reasoning_style', 'balanced'),
                relationship_to_user='advisor',
            ),
            cognitive_heuristics=CognitiveHeuristics(
                default_framework=v2_data.get('decision_framework', 'evidence_based'),
                heuristics=v2_data.get('heuristics', []),
            ),
            value_hierarchy=ValueHierarchy(
                values=v2_data.get('prioritized_values', []),
            ),
            # ... other layers
        )
        
        await create_persona_spec_v2(
            twin_id=twin_id,
            tenant_id=tenant_id,
            created_by=user_id,
            spec=persona_v2,
            status="active",  # Auto-publish
            source="onboarding",
        )
        
        # Enable 5-Layer for this twin
        supabase.table("twins").update({
            "settings": {
                **request.settings,
                "use_5layer_persona": True,
            }
        }).eq("id", twin_id).execute()
```

#### 1.2 Enhanced Persona Bootstrap from Onboarding

```python
# backend/modules/persona_onboarding_bootstrap.py

from modules.persona_spec_v2 import (
    PersonaSpecV2,
    IdentityFrame,
    CognitiveHeuristics,
    CognitiveHeuristic,
    ValueHierarchy,
    ValueItem,
    CommunicationPatterns,
    SafetyBoundary,
)

def bootstrap_persona_from_onboarding(onboarding_data: dict) -> PersonaSpecV2:
    """
    Convert onboarding form data to 5-Layer Persona Spec v2
    """
    
    # Layer 1: Identity Frame
    identity = IdentityFrame(
        role_definition=f"{onboarding_data['twin_name']} - {onboarding_data.get('tagline', '')}",
        expertise_domains=[
            *onboarding_data.get('selected_domains', []),
            *onboarding_data.get('custom_expertise', [])
        ],
        background_summary=onboarding_data.get('background', ''),
        reasoning_style=onboarding_data.get('reasoning_style', 'balanced'),
        relationship_to_user='advisor',
        communication_tendencies={
            "directness": onboarding_data.get('personality', {}).get('tone', 'friendly'),
            "verbosity": onboarding_data.get('personality', {}).get('response_length', 'balanced'),
        }
    )
    
    # Layer 2: Cognitive Heuristics
    heuristics = []
    
    # Infer heuristics from specialization
    specialization = onboarding_data.get('specialization', 'vanilla')
    if specialization == 'founder':
        heuristics.append(CognitiveHeuristic(
            id="founder_team_first",
            name="Team-First Evaluation",
            description="Prioritize founder quality in startup evaluations",
            applicable_query_types=["evaluation", "startup_assessment"],
            steps=["Evaluate founder background", "Assess domain fit", "Check team completeness"],
            priority=10,
        ))
    
    # Add heuristic from uncertainty preference
    if onboarding_data.get('uncertainty_preference') == 'ask':
        heuristics.append(CognitiveHeuristic(
            id="clarify_first",
            name="Clarify Before Answering",
            description="Ask clarifying questions when information is insufficient",
            applicable_query_types=["advice", "evaluation"],
            steps=["Assess information completeness", "Identify missing data", "Ask targeted questions"],
            priority=20,
        ))
    
    cognitive = CognitiveHeuristics(
        default_framework=onboarding_data.get('decision_framework', 'evidence_based'),
        heuristics=heuristics,
    )
    
    # Layer 3: Value Hierarchy
    # Convert goals to values with priority
    goals = onboarding_data.get('goals_90_days', [])
    values = []
    for i, goal in enumerate(goals):
        if goal.strip():
            values.append(ValueItem(
                name=f"goal_{i}",
                priority=i+1,
                description=goal,
            ))
    
    # Add default values based on specialization
    if specialization == 'founder':
        values.extend([
            ValueItem(name="team_quality", priority=10, description="Strong founding team"),
            ValueItem(name="market_size", priority=20, description="Large addressable market"),
            ValueItem(name="traction", priority=30, description="Evidence of PMF"),
        ])
    
    value_hierarchy = ValueHierarchy(
        values=values,
        scoring_dimensions=[
            {"name": "market", "description": "Market opportunity"},
            {"name": "founder", "description": "Team strength"},
            {"name": "traction", "description": "Product-market fit evidence"},
            {"name": "defensibility", "description": "Competitive moat"},
            {"name": "speed", "description": "Execution velocity"},
        ]
    )
    
    # Layer 4: Communication Patterns
    personality = onboarding_data.get('personality', {})
    communication = CommunicationPatterns(
        signature_phrases=[
            onboarding_data.get('signature_phrase', ''),
        ] if onboarding_data.get('signature_phrase') else [],
        brevity_preference=personality.get('response_length', 'balanced'),
        anti_patterns=[
            "As an AI language model",
            "I don't have personal opinions",
        ],
    )
    
    # Layer 5: Memory Anchors (empty initially, populated from documents)
    # ...
    
    # Safety Boundaries
    boundaries = []
    if onboarding_data.get('refuse_investment_advice', True):
        boundaries.append(SafetyBoundary(
            id="no_investment_promises",
            pattern=r"(should I invest|is this a good investment)",
            category="investment_promise",
            action="refuse",
            refusal_template="I can't provide investment advice, but I can share my perspective on the team and market.",
        ))
    
    return PersonaSpecV2(
        version="2.0.0",
        name=f"{onboarding_data['twin_name']} Persona",
        description=onboarding_data.get('tagline', ''),
        identity_frame=identity,
        cognitive_heuristics=cognitive,
        value_hierarchy=value_hierarchy,
        communication_patterns=communication,
        safety_boundaries=boundaries,
    )
```

### Phase 2: Frontend Changes

#### 2.1 Enhanced Step 1: Identity + Layer 1

```typescript
// frontend/components/onboarding/steps/Step1IdentityEnhanced.tsx

interface Step1IdentityEnhancedProps {
  // Existing props
  twinName: string;
  tagline: string;
  // ...
  
  // NEW: Layer 1 - Identity Frame
  roleDefinition: string;
  reasoningStyle: 'analytical' | 'intuitive' | 'balanced' | 'first_principles';
  relationshipType: 'mentor' | 'peer' | 'advisor' | 'collaborator';
  
  // NEW: Layer 2 - Cognitive Heuristics
  decisionFramework: string;
  evaluationCriteria: string[];
  
  // NEW: Layer 4 - Communication
  signaturePhrases: string[];
  antiPatterns: string[];
  
  // Callbacks
  onRoleDefinitionChange: (value: string) => void;
  onReasoningStyleChange: (value: string) => void;
  // ...
}

// Form Section: How I Think (Layer 2)
const CognitiveHeuristicsSection = () => (
  <div className="space-y-4">
    <h3 className="text-lg font-medium">How do you approach decisions?</h3>
    
    <RadioGroup
      label="Reasoning Style"
      value={reasoningStyle}
      onChange={onReasoningStyleChange}
      options={[
        { 
          value: 'analytical', 
          label: 'Analytical',
          description: 'Data-driven, methodical evaluation'
        },
        { 
          value: 'intuitive', 
          label: 'Intuitive',
          description: 'Pattern-based, experience-led'
        },
        { 
          value: 'first_principles', 
          label: 'First Principles',
          description: 'Break down to fundamentals'
        },
        { 
          value: 'balanced', 
          label: 'Balanced',
          description: 'Adaptive based on context'
        },
      ]}
    />
    
    <TextArea
      label="What do you look for first when evaluating something?"
      placeholder="e.g., 'I always look at the team first, then market size...'"
      value={evaluationCriteria}
      onChange={onEvaluationCriteriaChange}
    />
  </div>
);
```

#### 2.2 New Step: Values & Priorities (Layer 3)

```typescript
// frontend/components/onboarding/steps/Step3Values.tsx

export default function Step3Values({
  prioritizedValues,
  onValuesReorder,
  valueDefinitions,
  onValueDefinitionChange,
  conflictRules,
}: Step3ValuesProps) {
  
  const defaultValues = [
    { id: 'team_quality', name: 'Team Quality', description: 'Strong founding team' },
    { id: 'market_size', name: 'Market Size', description: 'Large TAM' },
    { id: 'traction', name: 'Traction', description: 'Evidence of PMF' },
    { id: 'defensibility', name: 'Defensibility', description: 'Competitive moat' },
    { id: 'speed', name: 'Speed', description: 'Execution velocity' },
  ];
  
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold">What do you prioritize?</h2>
        <p className="text-gray-600">
          Rank these values by importance. Your twin will use this to resolve conflicts.
        </p>
      </div>
      
      {/* Draggable Value List */}
      <DragDropContext onDragEnd={onValuesReorder}>
        <Droppable droppableId="values">
          {(provided) => (
            <div {...provided.droppableProps} ref={provided.innerRef} className="space-y-2">
              {prioritizedValues.map((value, index) => (
                <Draggable key={value.id} draggableId={value.id} index={index}>
                  {(provided) => (
                    <div
                      ref={provided.innerRef}
                      {...provided.draggableProps}
                      {...provided.dragHandleProps}
                      className="flex items-center gap-4 p-4 bg-white border rounded-lg shadow-sm"
                    >
                      <span className="text-2xl font-bold text-gray-400">#{index + 1}</span>
                      <div className="flex-1">
                        <h4 className="font-medium">{value.name}</h4>
                        <p className="text-sm text-gray-500">{value.description}</p>
                      </div>
                      <GripVertical className="text-gray-400" />
                    </div>
                  )}
                </Draggable>
              ))}
              {provided.placeholder}
            </div>
          )}
        </Droppable>
      </DragDropContext>
      
      {/* Scoring Dimensions */}
      <div className="mt-8">
        <h3 className="text-lg font-medium mb-4">Define your scoring criteria</h3>
        <p className="text-sm text-gray-600 mb-4">
          When evaluating opportunities, you'll score 1-5 on these dimensions.
          What does each score mean to you?
        </p>
        
        {defaultValues.map((value) => (
          <ScoringDimensionConfig
            key={value.id}
            name={value.name}
            definitions={valueDefinitions[value.id]}
            onChange={(defs) => onValueDefinitionChange(value.id, defs)}
          />
        ))}
      </div>
    </div>
  );
}
```

#### 2.3 Persona Preview Component

```typescript
// frontend/components/onboarding/PersonaPreview.tsx

export default function PersonaPreview({ personaData }: PersonaPreviewProps) {
  return (
    <div className="bg-gray-50 rounded-xl p-6 space-y-6">
      <h3 className="text-lg font-medium">Your Persona Preview</h3>
      
      {/* Layer 1: Identity */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-500 uppercase">Identity</h4>
        <div className="bg-white p-4 rounded-lg">
          <p className="font-medium">{personaData.twinName}</p>
          <p className="text-sm text-gray-600">{personaData.roleDefinition}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {personaData.expertise.map((exp) => (
              <span key={exp} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                {exp}
              </span>
            ))}
          </div>
        </div>
      </div>
      
      {/* Layer 3: Value Hierarchy */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-500 uppercase">Value Priority</h4>
        <div className="bg-white p-4 rounded-lg">
          <ol className="space-y-2">
            {personaData.prioritizedValues.map((value, i) => (
              <li key={value.id} className="flex items-center gap-2">
                <span className="w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm">
                  {i + 1}
                </span>
                <span>{value.name}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
      
      {/* Sample Output */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-500 uppercase">Sample Response</h4>
        <div className="bg-white p-4 rounded-lg border-l-4 border-blue-500">
          <p className="text-sm italic text-gray-600">
            "Here's the thing... This looks promising from a team perspective. 
            I'd score them 4/5 on founder quality, though the market is still unproven at 3/5."
          </p>
          <div className="mt-2 flex gap-4 text-xs text-gray-500">
            <span>market: 3/5</span>
            <span>founder: 4/5</span>
            <span>traction: 2/5</span>
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## API Changes Required

### New Endpoint: Bootstrap Persona from Onboarding

```typescript
// POST /twins/{twin_id}/persona-specs/bootstrap-from-onboarding

interface BootstrapPersonaRequest {
  // Layer 1: Identity
  role_definition: string;
  expertise_domains: string[];
  reasoning_style: 'analytical' | 'intuitive' | 'balanced' | 'first_principles';
  relationship_to_user: 'mentor' | 'peer' | 'advisor' | 'collaborator';
  
  // Layer 2: Cognitive Heuristics
  decision_framework: string;
  heuristics: {
    id: string;
    name: string;
    description: string;
    applicable_query_types: string[];
  }[];
  
  // Layer 3: Value Hierarchy
  prioritized_values: {
    name: string;
    priority: number;
    description: string;
  }[];
  scoring_dimensions: {
    name: string;
    description: string;
    weight: number;
  }[];
  
  // Layer 4: Communication
  signature_phrases: string[];
  brevity_preference: 'concise' | 'moderate' | 'detailed';
  
  // Layer 5: Memory (optional)
  initial_memories?: {
    type: 'experience' | 'lesson' | 'principle';
    content: string;
  }[];
}

// Response
interface BootstrapPersonaResponse {
  status: 'active';
  persona_spec_version: '2.0.0';
  persona_spec: PersonaSpecV2;
  twin_settings_updated: boolean;
  use_5layer_persona_enabled: true;
}
```

---

## Migration Strategy

### For Existing Twins

```python
# backend/scripts/migrate_twins_to_persona_v2.py

async def migrate_twin_to_v2(twin_id: str):
    """
    Convert existing twin's settings to 5-Layer Persona v2
    """
    # Get existing twin
    twin = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
    settings = twin.data.get("settings", {})
    
    # Parse existing system_prompt
    system_prompt = settings.get("system_prompt", "")
    
    # Extract data using LLM or regex
    extracted = {
        "role_definition": extract_role(system_prompt),
        "expertise": extract_expertise(system_prompt),
        "tone": extract_tone(system_prompt),
        "goals": extract_goals(system_prompt),
    }
    
    # Create v2 persona
    persona_v2 = bootstrap_persona_from_legacy_data(extracted)
    
    # Save
    await create_persona_spec_v2(
        twin_id=twin_id,
        spec=persona_v2,
        status="active",
        source="migration",
    )
    
    # Enable flag
    supabase.table("twins").update({
        "settings": {
            **settings,
            "use_5layer_persona": True,
        }
    }).eq("id", twin_id).execute()
```

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Persona Spec Creation Rate | < 5% | 100% |
| Time to First Evaluation | N/A | < 2 min after onboarding |
| User Satisfaction | Unknown | > 4.0/5.0 |
| Consistency Score | N/A | > 90% |

---

## Summary

### Current State
- ✅ Rich onboarding data collected
- ❌ Data flattened to text
- ❌ 5-Layer Persona never created
- ❌ Structured decision-making unavailable

### Target State
- ✅ Rich onboarding data collected
- ✅ Data structured into 5-Layer Persona
- ✅ Automatic v2 spec creation
- ✅ Structured, scored, consistent responses from day 1

### Action Items
1. **Backend**: Create `bootstrap_persona_from_onboarding()` function
2. **Backend**: Modify twin creation to auto-create v2 persona
3. **Frontend**: Add new onboarding steps for Layers 2 & 3
4. **Frontend**: Create Persona Preview component
5. **Migration**: Script to convert existing twins
6. **Testing**: Verify 5-Layer Persona activates immediately after onboarding

**Estimated Effort:** 2-3 weeks  
**Impact:** Critical - Unlocks core value proposition of the product
