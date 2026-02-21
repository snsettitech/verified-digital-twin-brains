# Profile Tab Integration into 5-Layer Persona

## Current Gap Analysis

### Profile Tab Contains (High-Value Data):
```typescript
interface ProfileData {
  displayName: string;        // "Alex Chen"
  organization: string;       // "TechVentures Inc"
  role: string;              // "Founder & CEO"  
  headline: string;          // "Building the future of AI"
  bio: string;               // "Former Google PM, 3x founder..."
  pinnedQuestions: string[]; // FAQs the twin should handle
  socialLinks: string[];     // External presence
  avatarUrl: string;
  profileVideoEnabled: boolean;
}
```

### Current Onboarding Step 1 Collects:
```typescript
interface CurrentIdentity {
  twinName: string;          // "Alex's Twin"
  tagline: string;          // "Startup founder..."
  expertise: string[];      // Selected domains
  goals90Days: string[];
  boundaries: string;
}
```

**Gap**: Profile has richer professional context that improves persona authenticity!

---

## Integration Plan

### Option A: Expand Step 1 (Recommended)

Add Profile fields to **Layer 1: Identity Frame**:

```typescript
// Enhanced Step 1 collects:
interface EnhancedIdentity {
  // Basic (existing)
  twinName: string;
  handle: string;
  
  // Professional Profile (NEW)
  displayName: string;       // Full name for role definition
  organization: string;      // Company/brand
  role: string;             // Job title/position
  headline: string;         // One-line description
  bio: string;              // Full background story
  
  // Expertise (existing)
  expertise: string[];
  customExpertise: string[];
  
  // Engagement (NEW from Profile)
  pinnedQuestions: string[]; // What users typically ask
  socialLinks: string[];    // Where to find more info
  
  // Goals & Boundaries (existing)
  goals90Days: string[];
  boundaries: string;
}
```

### Mapping to 5-Layer Schema

```typescript
// Layer 1: Identity Frame
identity_frame: {
  role_definition: `${displayName} - ${role} at ${organization}. ${headline}`,
  expertise_domains: [...expertise, ...customExpertise],
  background_summary: bio,  // Rich bio from Profile
  reasoning_style: "...",
  relationship_to_user: "...",
  communication_tendencies: {
    // Inferred from pinnedQuestions + bio tone
  }
}

// Layer 2: Cognitive Heuristics  
cognitive_heuristics: {
  heuristics: [
    {
      id: "pinned_question_handler",
      name: "Handle Common Questions",
      description: "Answer frequently asked questions based on pinned topics",
      applicable_types: ["faq", "smalltalk"],
      // Uses pinnedQuestions from Profile
    }
  ]
}

// Layer 5: Memory Anchors (NEW from Profile)
memory_anchors: {
  anchors: [
    // Convert bio into experience anchors
    {
      type: "experience",
      content: bio,
      context: "Professional background",
      tags: ["background", "credentials"]
    },
    // Each pinned question becomes an anchor
    ...pinnedQuestions.map(q => ({
      type: "lesson",
      content: q,
      context: "Frequently asked question",
      tags: ["faq", "engagement"]
    }))
  ]
}
```

---

## UI Mockup: Enhanced Step 1

```
┌─────────────────────────────────────────────────────────┐
│  STEP 1: LAYER 1 - IDENTITY FRAME                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─ PROFESSIONAL IDENTITY ──────────────────────────┐  │
│  │                                                   │  │
│  │  Full Name *        Organization                │  │
│  │  [Alex Chen    ]    [TechVentures Inc   ]       │  │
│  │                                                   │  │
│  │  Role/Title         Headline                     │  │
│  │  [Founder & CEO]    [Building AI infrastructure] │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ BACKGROUND STORY ───────────────────────────────┐  │
│  │                                                   │  │
│  │  Bio / Public Introduction                       │  │
│  │  ┌─────────────────────────────────────────┐     │  │
│  │  │ Former Google PM, now building my 3rd   │     │  │
│  │  │ startup. Obsessed with AI infrastructure │     │  │
│  │  │ and developer tools...                  │     │  │
│  │  └─────────────────────────────────────────┘     │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ ENGAGEMENT ─────────────────────────────────────┐  │
│  │                                                   │  │
│  │  Pinned Questions (Max 5)                        │  │
│  │  These are questions people typically ask you    │  │
│  │  [What inspired you to start?                 ] X │  │
│  │  [What's your approach to product management? ] X │  │
│  │  [How do you think about AI infrastructure?   ] X │  │
│  │  [+ Add Question]                                │  │
│  │                                                   │  │
│  │  Social Links                                    │  │
│  │  [linkedin.com/in/alexchen] [twitter.com/alex]   │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  [Next: Thinking Style →]                               │
└─────────────────────────────────────────────────────────┘
```

---

## Benefits of Integration

### 1. **Richer Persona Context**
- `bio` → Provides detailed background for `identity_frame.background_summary`
- `organization + role` → More specific `role_definition` than generic tagline
- `headline` → Professional positioning

### 2. **Better FAQ Handling**
- `pinnedQuestions` → Auto-generate Layer 2 heuristics for common questions
- Twin can proactively reference these in conversations

### 3. **Memory Anchors from Bio**
- Parse bio into key experiences for Layer 5
- "Former Google PM" → Experience anchor
- "3rd startup" → Pattern anchor about entrepreneurship

### 4. **Consistent Public Profile**
- Profile data collected during onboarding = Profile tab data
- No duplication, single source of truth

---

## Implementation Priority

**P0 (Critical)**: Add `bio`, `organization`, `role` to Step 1
- These significantly improve `identity_frame` quality
- Easy to collect, high impact

**P1 (High)**: Add `pinnedQuestions`
- Creates Layer 2 heuristics automatically
- Helps twin handle common queries

**P2 (Medium)**: Add `socialLinks`
- Can be used for credibility/context
- Lower impact on persona behavior

---

## Backend Changes Needed

1. **Update `persona_bootstrap.py`**:
   - Map new fields to Identity Frame
   - Generate heuristics from pinnedQuestions
   - Create memory anchors from bio

2. **Update `TwinCreateRequest` schema**:
   - Add profile fields to `persona_v2_data`

3. **Sync with Profile tab**:
   - Onboarding saves to same `settings.public_profile` location
   - Profile tab reads from same location
