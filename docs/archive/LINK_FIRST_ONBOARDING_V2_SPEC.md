# Low-Friction Link-First Onboarding Flow

## Overview

A redesigned onboarding flow that optimizes for **low friction** (2 minutes to first value) and **high trust** (verified, citable persona).

## Design Principles

1. **Progressive Disclosure**: Show only essential inputs upfront, defer advanced setup
2. **Identity Disambiguation**: User-confirmed matching (names are ambiguous)
3. **Privacy by Design**: Explicit consent, data minimization, transparency
4. **Conservative Web Fetch**: Allowlists/blocklists, export/paste preferred
5. **No Long Tutorials**: Contextual help instead of interruptive guides

## User Journey

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Welcome   │────▶│ Link Suggestions│────▶│ Add Sources  │
│ (1 minute)  │     │  (30 seconds)   │     │ (30 seconds) │
└─────────────┘     └─────────────────┘     └──────────────┘
                                                     │
                        ┌─────────────────────────────┘
                        ▼
               ┌────────────────┐     ┌─────────────────┐
               │    Building    │────▶│ Profile Landing │
               │  (1-2 minutes) │     │  (Activate CTA) │
               └────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                               ┌────────────────┐
                                               │  Chat (Active) │
                                               └────────────────┘
```

## Screen-by-Screen Specification

### 1. Welcome Screen

**Purpose**: Capture identity + consent, create draft twin

**Fields**:
- **Full Name*** (required): Primary search key
- **Location** (optional): Disambiguation signal
- **Current Role** (optional): Disambiguation signal
- **Consent checkbox***: "Search the public web for links that look like me"

**UX Details**:
- Shows data policy: "We search public sources only. Unselected results not stored."
- "Prefer manual setup?" link switches to 6-step flow
- Creates twin in `draft` status immediately

**Backend**: `POST /twins` with `mode=link_first`

---

### 2. Link Suggestions

**Purpose**: User-confirmed identity matching (disambiguation)

**Content**:
- Search results with **confidence labels** (high/medium/low)
- **Match signals** displayed (e.g., "Exact name match", "Location match")
- **"This is me"** / **"Not me"** actions on each result

**UX Details**:
- High confidence pre-selected
- Filter tabs: All / High / Medium / Low
- Quick actions: "Select all high-confidence", "Clear all"
- Skip option: "Add manually instead"

**Why This Screen**: Name-based matching is error-prone. Entity resolution requires explicit confirmation.

**Backend**: `GET /persona/link-compile/suggest?name={name}&location={loc}&role={role}`

---

### 3. Add Sources

**Purpose**: Unified source input (exports + links + paste)

**Tabs**:
1. **Exports** (recommended): Upload LinkedIn/Twitter archives, PDFs, HTML
2. **Links**: Categorized by type (Social, Dev/Portfolio, Writing, Press)
3. **Paste**: Text input for bios, resumes, about pages

**UX Details**:
- Category quick-add buttons (Social, Dev, Writing, Press)
- Privacy note: "Raw exports processed and deleted. Only claims stored."
- Shows source count and types

**Backend**:
- Files: `POST /persona/link-compile/jobs/mode-a`
- Paste: `POST /persona/link-compile/jobs/mode-b`
- URLs: `POST /persona/link-compile/jobs/mode-c`

---

### 4. Building

**Purpose**: Show progress while system processes sources

**Two-Track Progress**:
1. **Collecting Sources**: Download/process (blue bar)
2. **Extracting Claims & Bio**: NLP + generation (indigo bar)

**UX Details**:
- Real-time stats: sources processed, claims found
- Status messages: "Downloading...", "Extracting claims...", "Generating bio..."
- Tips: "More high-quality sources = more accurate twin"

**Backend**: Poll `GET /persona/link-compile/twins/{id}/job`

---

### 5. Profile Landing

**Purpose**: First value delivery + activation decision

**Content**:
- **Auto-generated bio**: Short/medium/LinkedIn/speaker variants
- **Sources list**: What was used (with +Add More)
- **Evidence panel** (collapsible):
  - Verified claims count
  - Needs confirmation count
  - Disputed claims count
- **Activate CTA**: "Chat with Your Twin"

**UX Details**:
- Bio type selector (tabs)
- Can review claims before activating
- Can add more sources
- "You can always improve later" reassurance

**Backend**: 
- Bios: `GET /persona/link-compile/twins/{id}/bios`
- Claims: `GET /persona/link-compile/twins/{id}/claims`

---

### 6. Chat (Active Twin)

**Purpose**: First interaction with Digital Twin

**Progressive Enrichment** (post-chat):
- Contextual prompts for claim review
- Clarification interview for low-confidence items
- Source addition prompts

## State Machine

```
draft ──▶ ingesting ──▶ claims_ready ──▶ [profile] ──▶ active
            │                              │
            └─ User submits sources        ├─ User clicks "Activate"
                                           └─ Or reviews claims first
```

**Note**: `clarification_pending` and `persona_built` states are still supported but now accessed via Profile Landing (progressive enrichment) rather than blocking activation.

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/twins` | POST | Create twin (mode=link_first/manual) |
| `/persona/link-compile/suggest` | GET | Search for candidate links |
| `/persona/link-compile/jobs/mode-a` | POST | Upload exports |
| `/persona/link-compile/jobs/mode-b` | POST | Paste content |
| `/persona/link-compile/jobs/mode-c` | POST | Fetch URLs |
| `/persona/link-compile/twins/{id}/job` | GET | Poll job progress |
| `/persona/link-compile/twins/{id}/bios` | GET | Get bio variants |
| `/persona/link-compile/twins/{id}/claims` | GET | Get claims |
| `/twins/{id}/activate` | POST | Activate twin |

## Privacy Controls

1. **Welcome**: Explicit consent checkbox with explanation
2. **Add Sources**: "Raw exports deleted after processing" note
3. **Profile**: Sources list with delete option
4. **Data Policy**: Transparent about what is searched vs stored

## Metrics to Track

| Metric | Target | Purpose |
|--------|--------|---------|
| Time to first bio | < 3 minutes | Friction measurement |
| Link suggestion acceptance rate | > 60% | Identity match quality |
| Source submission rate | > 80% | Engagement |
| Activation rate | > 70% | Conversion |
| Claim dispute rate | < 10% | Quality indicator |
| Manual flow usage | < 20% | Link-first preference |

## Files Changed

| File | Lines | Purpose |
|------|-------|---------|
| `StepWelcome.tsx` | 150 | Welcome screen with consent |
| `StepLinkSuggestions.tsx` | 280 | Disambiguation UI |
| `StepAddSources.tsx` | 320 | Unified source input |
| `StepBuilding.tsx` | 200 | Two-track progress |
| `StepProfileLanding.tsx` | 280 | Profile + activation |
| `page.tsx` | 550 | Main flow orchestration |
| `persona_link_compile.py` | +50 | Suggest endpoint |

## Testing Checklist

- [ ] Welcome creates draft twin with consent
- [ ] Link suggestions show confidence + match signals
- [ ] "Not me" removes candidate
- [ ] Add Sources handles exports/links/paste
- [ ] Building shows two-track progress
- [ ] Profile shows bio + evidence panel
- [ ] Activation creates persona spec
- [ ] Chat works after activation
- [ ] Manual flow still works (regression)
- [ ] Resume onboarding from any state
