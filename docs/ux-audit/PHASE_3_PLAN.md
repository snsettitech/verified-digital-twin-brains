# Phase 3 Implementation Plan

**Date:** February 9, 2026  
**Status:** Planning  

---

## Overview

Phase 3 implements advanced features that require deeper backend integration and complex state management:
1. Training/Jobs Progress Indicator (UX-010)
2. Voice Settings UI
3. Knowledge Graph Zoom/Pan
4. Additional Dashboard Empty States

---

## Feature 1: Training/Jobs Progress Indicator (UX-010)

### Backend Analysis

**Available Endpoints:**
```
GET /jobs?twin_id={twin_id}&status={status}     - List jobs
GET /jobs/{job_id}                               - Job details
GET /jobs/{job_id}/logs                          - Job logs
GET /twins/{twin_id}/training-sessions/active    - Active training
```

**Job Statuses:**
- `queued` - Waiting to start
- `processing` - Currently running
- `needs_attention` - Blocked/needs help
- `complete` - Finished successfully
- `failed` - Error occurred

**Job Types:**
- `ingestion` - Source ingestion
- `reindex` - Vector reindexing
- `graph_extraction` - Graph building
- `content_extraction` - Text extraction
- `feedback_learning` - Model improvement

### Edge Cases Analysis

| Edge Case | Impact | Solution |
|-----------|--------|----------|
| **No active jobs** | Empty state | Show "No active jobs" + create button |
| **Job status unknown** | UI confusion | Polling with exponential backoff |
| **Multiple concurrent jobs** | Which to show? | Show all in list, expand for details |
| **Job fails** | User notification | Error banner with retry button |
| **Job stuck in processing** | Infinite spinner | Timeout after 30 min, mark as needs_attention |
| **Network drops during poll** | Missed updates | Retry with exponential backoff |
| **User navigates away** | Polling continues | Cleanup on unmount |
| **Job completes** | Notification | Success toast + confetti |
| **Large number of jobs** | Performance | Pagination (limit 10) |
| **Job logs are huge** | Slow loading | Limit logs to last 50 entries |

### Implementation Plan

**Files to create:**
- `frontend/components/jobs/JobProgress.tsx` - Job progress component
- `frontend/components/jobs/JobsList.tsx` - List of jobs
- `frontend/lib/hooks/useJobPolling.ts` - Polling hook

**Files to modify:**
- `frontend/components/console/tabs/TrainingTab.tsx` - Add progress UI
- `frontend/app/dashboard/jobs/page.tsx` - Jobs dashboard (new)

**Polling Strategy:**
```typescript
// Polling intervals based on status
const POLL_INTERVALS = {
  queued: 5000,      // Check every 5s
  processing: 3000,  // Check every 3s
  needs_attention: 10000,  // Check every 10s
  complete: 0,       // Stop polling
  failed: 0,         // Stop polling
};

// Exponential backoff on errors
// Max interval: 30 seconds
// Cleanup on unmount
```

**Component Design:**
```typescript
interface JobProgressProps {
  twinId: string;
  jobId?: string;  // If not provided, shows active job
}

// Features:
// - Progress bar with percentage
// - Step indicators (if steps available in metadata)
// - Status badge (color-coded)
// - Log viewer (collapsible)
// - Estimated time remaining
// - Cancel button (if cancelable)
// - Retry button (if failed)
```

### Testing Checklist
- [ ] Shows loading on initial fetch
- [ ] Updates when job status changes
- [ ] Handles job failure with retry
- [ ] Stops polling when complete
- [ ] Shows estimated time
- [ ] Log viewer works
- [ ] Cancel job functionality
- [ ] Multiple jobs display correctly

---

## Feature 2: Voice Settings UI

### Backend Analysis

**Available Endpoints:**
```
GET /audio/voices              - List available voices
GET /audio/settings/{twin_id}  - Get current settings
PUT /audio/settings/{twin_id}  - Update settings
```

**Settings Structure:**
```typescript
{
  voice_id: string;
  model_id: string;
  stability: number;        // 0-1
  similarity_boost: number; // 0-1
  style: number;            // 0-1
  use_speaker_boost: boolean;
}
```

### Edge Cases Analysis

| Edge Case | Impact | Solution |
|-----------|--------|----------|
| **No voices available** | Empty dropdown | Show error + retry button |
| **API key missing** | TTS won't work | Show warning banner |
| **Invalid voice ID** | Error on save | Validation before submit |
| **Test voice fails** | User confusion | Error message in test player |
| **Long text test** | Rate limiting | Limit test to 200 chars |
| **Settings save fails** | Data loss | Optimistic UI + rollback |
| **Concurrent edits** | Overwrites | Last-write-wins (acceptable) |

### Implementation Plan

**Files to create:**
- `frontend/components/settings/VoiceSettings.tsx`

**Files to modify:**
- `frontend/app/dashboard/settings/page.tsx` - Add voice tab

**Features:**
- Voice dropdown with preview
- Stability slider (0-1)
- Similarity boost slider (0-1)
- Style slider (0-1)
- Speaker boost toggle
- Test voice button
- Save/Cancel actions

---

## Feature 3: Knowledge Graph Zoom/Pan

### Current Limitations
- Fixed view
- No zoom
- No pan
- Nodes can go off-screen

### Edge Cases Analysis

| Edge Case | Impact | Solution |
|-----------|--------|----------|
| **Zoom too far in** | Lost context | Min zoom: 0.5x, Max: 3x |
| **Pan off-screen** | Lost graph | Constrain pan to bounds |
| **Node selected while zoomed** | Label off-screen | Auto-pan to node |
| **Resize while zoomed** | Scale issues | Reset zoom on resize |
| **Touch device** | No wheel zoom | Add pinch zoom |
| **Many nodes** | Performance | Virtualization (show visible only) |

### Implementation Plan

**Files to modify:**
- `frontend/components/Knowledge/KnowledgeGraph.tsx`

**Features:**
- Mouse wheel zoom
- Click-drag pan
- Zoom in/out buttons
- Reset view button
- Minimap (optional)
- Fit to screen button

---

## Feature 4: Additional Empty States

### Missing Empty States
1. **Dashboard - No twins created yet**
2. **Share page - First time setup**
3. **Metrics/Insights - No data yet**
4. **API Keys - No keys created**

### Implementation
Extend existing `EmptyState` component with new illustrations.

---

## Implementation Order

1. **Jobs Progress** (Highest complexity, most requested)
   - Hook first
   - Component second
   - Integration third
   - Testing fourth

2. **Voice Settings** (Medium complexity)
   - Form design
   - API integration
   - Test player

3. **Graph Zoom/Pan** (Lower priority)
   - Transform logic
   - Event handlers
   - Constraints

4. **Additional Empty States** (Quick wins)
   - New illustrations
   - Integration

---

## Risk Assessment

| Feature | Risk | Mitigation |
|---------|------|------------|
| Jobs Progress | High (polling complexity) | Exponential backoff, cleanup |
| Voice Settings | Low | Well-defined API |
| Graph Zoom | Medium | Transform math |
| Empty States | Low | Pure frontend |

---

## Success Criteria

- [ ] Jobs progress updates in real-time
- [ ] No memory leaks from polling
- [ ] Voice settings save correctly
- [ ] Graph zoom/pan is smooth
- [ ] All empty states have CTAs
