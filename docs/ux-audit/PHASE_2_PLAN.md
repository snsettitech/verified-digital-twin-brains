# Phase 2 Implementation Plan

**Date:** February 9, 2026  
**Status:** Planning Complete  

---

## Overview

Phase 2 implements 3 UX improvements:
1. Dynamic Suggested Questions (UX-002, UX-018)
2. Training Progress Indicator (UX-010)
3. Empty State Illustrations (UX-014)

---

## Feature 1: Dynamic Suggested Questions (UX-002, UX-018)

### Current State
Chat interface shows static questions:
```typescript
const suggestedQuestions = [
  'What can you help me with?',
  'Tell me about yourself',
  'What do you know?'
];
```

### Target State
- Fetch questions from `/metrics/top-questions/{twin_id}`
- Display as clickable chips
- Update based on twin's actual knowledge

### Edge Cases Analysis

| Edge Case | Impact | Solution |
|-----------|--------|----------|
| **No questions available** | Empty chips section | Show default fallback questions |
| **API returns < 5 questions** | Fewer chips shown | Show available + "Ask anything" prompt |
| **API error** | Broken UI | Show fallback + silent error |
| **User clicks question** | Should populate input | Input field update with click-to-send |
| **Questions loading** | Flash of empty state | Skeleton shimmer while loading |
| **Knowledge updated** | Questions may be stale | Refresh on knowledge change |
| **First-time twin** | No conversation history | Show onboarding questions |

### Implementation Plan

**Files to modify:**
- `frontend/components/Chat/ChatInterface.tsx` - Add question chips
- `frontend/components/Chat/SuggestedQuestions.tsx` - New component

**API Integration:**
```typescript
GET /metrics/top-questions/{twin_id}
Response: {
  questions: [
    { question: string, count: number, avg_confidence: number }
  ]
}
```

**Component Design:**
```typescript
interface SuggestedQuestionsProps {
  twinId: string;
  onSelect: (question: string) => void;
  disabled?: boolean;
}

// Features:
// - Horizontal scrollable chips
// - Click to populate input
// - Loading skeleton
// - Error fallback
// - Empty state with default questions
```

### Testing Checklist
- [ ] Questions load on component mount
- [ ] Clicking question populates input
- [ ] Loading state shows skeleton
- [ ] Error shows fallback questions
- [ ] Empty response shows defaults
- [ ] Chips are keyboard accessible
- [ ] Mobile: horizontal scroll works

---

## Feature 2: Training Progress Indicator (UX-010)

### Current State
TrainingTab shows cards but no step-by-step progress for active training.

### Target State
- Show active training job status
- Progress bar with steps
- Real-time or polling updates
- Completion/error states

### Edge Cases Analysis

| Edge Case | Impact | Solution |
|-----------|--------|----------|
| **No active training** | What to show? | Show "No active training" + start button |
| **Training just started** | Initial state | Show "Initializing..." step |
| **Training failed** | Error handling | Show error step with retry button |
| **Multiple training jobs** | Which to show? | Show most recent active, queue others |
| **Training completes** | Notification | Show completion + next steps |
| **Page refreshed** | State lost? | Fetch current status from API |
| **Long-running training** | User leaves page | Poll every 5 seconds for updates |
| **Training stuck** | Infinite loading | Timeout after 30 min, show error |

### Implementation Plan

**Files to modify:**
- `frontend/components/console/tabs/TrainingTab.tsx` - Add progress UI
- `frontend/components/training/TrainingProgress.tsx` - New component

**API Integration:**
```typescript
// Need to verify if this endpoint exists
GET /training/{twin_id}/status
// OR use existing jobs endpoint
GET /jobs?type=training&twin_id={twin_id}

Response: {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number; // 0-100
  current_step: string;
  steps: [
    { name: string, status: 'pending' | 'running' | 'completed' | 'failed' }
  ];
  error?: string;
  started_at: string;
  estimated_completion?: string;
}
```

**Component Design:**
```typescript
interface TrainingProgressProps {
  twinId: string;
  jobId?: string;
}

// Features:
// - Step indicator (vertical or horizontal)
// - Progress percentage
// - Current step description
// - Estimated time remaining
// - Cancel button
// - Error retry
// - Completion celebration
```

**Polling Strategy:**
```typescript
// Poll every 5 seconds while training is active
// Stop polling when:
// - Status is 'completed' or 'failed'
// - Component unmounts
// - User navigates away
// Backoff: If error, retry after 10s, then 30s
```

### Testing Checklist
- [ ] Progress shows on active training
- [ ] Steps update as training progresses
- [ ] Error state shows retry button
- [ ] Completion shows success message
- [ ] Polling stops when complete
- [ ] Polling stops on unmount
- [ ] Works with multiple concurrent trainings

---

## Feature 3: Empty State Illustrations (UX-014)

### Current State
Dashboard shows "0" values and empty lists with no visual treatment.

### Target State
- Illustrated empty states
- Contextual CTAs
- Helpful copy
- First-time user guidance

### Edge Cases Analysis

| Edge Case | Impact | Solution |
|-----------|--------|----------|
| **First-time user** | Needs guidance | Show "Get started" CTA prominently |
| **Returning user, empty** | Different context | Show "Add your first..." |
| **Loading vs empty** | Confusion | Skeleton loading first, then empty state |
| **Error loading data** | Wrong empty state | Show error, not empty |
| **Partial data** | Some cards empty | Individual empty states per card |
| **Mobile viewport** | Illustration size | Responsive illustrations |
| **Dark mode** | Colors mismatch | Dark mode compatible illustrations |

### Empty States Needed

1. **Dashboard - No twin created**
   - Illustration: Building blocks / robot being built
   - Copy: "Create your first digital twin"
   - CTA: "Get Started" button

2. **Dashboard - Twin exists but no activity**
   - Illustration: Sleeping robot / waiting
   - Copy: "Your twin is ready but hasn't chatted yet"
   - CTA: "Test your twin" link

3. **Knowledge - No sources**
   - Already implemented (partially)
   - Enhance with better illustration

4. **Escalations - Empty**
   - Illustration: Checkmark / clean inbox
   - Copy: "You're all caught up!"
   - CTA: "Test your twin" (optional)

5. **Chat - First open**
   - Suggested questions (handled in Feature 1)
   - Welcome message from twin

### Implementation Plan

**Files to modify:**
- `frontend/app/dashboard/page.tsx` - Dashboard empty states
- `frontend/app/dashboard/escalations/page.tsx` - Escalations empty state
- `frontend/components/ui/EmptyState.tsx` - Reusable component

**Component Design:**
```typescript
interface EmptyStateProps {
  illustration: 'robot-building' | 'robot-sleeping' | 'checkmark' | 'inbox-empty';
  title: string;
  description: string;
  primaryAction?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
  secondaryAction?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
}

// SVG illustrations (inline for no external dependencies)
// - Simple, line-art style
// - Animated with CSS (subtle pulse/bounce)
// - Dark mode compatible
```

### Testing Checklist
- [ ] Empty state shows when no data
- [ ] Loading state shows first
- [ ] CTA buttons work
- [ ] Responsive on mobile
- [ ] Dark mode compatible
- [ ] Error state different from empty

---

## Implementation Order

1. **Empty State Illustrations** (Easiest, high impact)
   - Build reusable component
   - Add to Dashboard
   - Add to Escalations
   
2. **Suggested Questions** (Medium complexity)
   - Build component
   - Integrate with ChatInterface
   - Test all edge cases
   
3. **Training Progress** (Hardest, needs backend verification)
   - Verify API endpoints
   - Build progress component
   - Add polling logic
   - Test with real training jobs

---

## Risk Assessment

| Feature | Risk Level | Mitigation |
|---------|-----------|------------|
| Suggested Questions | Low | Backend endpoint exists, well-defined scope |
| Empty States | Low | Pure frontend, no dependencies |
| Training Progress | Medium | API endpoint needs verification, polling complexity |

---

## Success Criteria

- All edge cases handled with tests
- No console errors
- Mobile responsive
- Accessibility verified (keyboard, screen reader)
- Dark mode compatible
