# Frontend State Model

**Last Updated:** 2026-02-04  
**Product:** Clone-for-Experts (Web-Only)  
**Status:** PLAN ONLY

---

## Overview

This document specifies the UI state model for all pages in the Clone-for-Experts application. Every page must handle five states:

1. **Loading** - Data is being fetched
2. **Empty** - No data exists
3. **Error** - Request failed
4. **Retry** - User can retry failed request
5. **Success** - Data loaded and displayed

---

## State Handling Patterns

### Current Implementation Analysis

| Component | Loading | Empty | Error | Retry | Notes |
|-----------|---------|-------|-------|-------|-------|
| `Skeleton.tsx` | ✅ | - | - | - | Good variety of presets |
| `EmptyState.tsx` | - | ✅ | ✅ | ✅ | Has action buttons |
| `ErrorBoundary.tsx` | - | - | ✅ | ✅ | Has refresh button |
| `Toast.tsx` | - | - | ✅ | - | Notification only |
| `SyncStatusBanner.tsx` | ✅ | - | ✅ | ✅ | Connection status |

### Gaps Identified

1. **Inconsistent loading states** - Some pages use skeleton, others use spinner
2. **Missing retry on some error states** - Not all errors offer retry
3. **No correlation ID display** - Errors don't show debugging info
4. **Inconsistent empty state copy** - Different wording across pages

---

## Recommended State Model

### Standard State Interface

```typescript
interface PageState<T> {
  status: 'loading' | 'empty' | 'error' | 'success';
  data: T | null;
  error: {
    message: string;
    code?: string;
    correlationId?: string;
    canRetry: boolean;
  } | null;
  lastUpdated: Date | null;
}
```

### Standard State Transitions

```
          ┌──────────────┐
          │   INITIAL    │
          └──────┬───────┘
                 │ mount
                 ▼
          ┌──────────────┐
    ┌─────│   LOADING    │─────┐
    │     └──────────────┘     │
    │ success                  │ error
    ▼                          ▼
┌──────────────┐        ┌──────────────┐
│   SUCCESS    │        │    ERROR     │
│  (or EMPTY)  │        │  (canRetry)  │
└──────────────┘        └──────┬───────┘
    │                          │
    │ refetch                  │ retry
    └──────────┐    ┌──────────┘
               ▼    ▼
          ┌──────────────┐
          │   LOADING    │
          └──────────────┘
```

---

## Page-by-Page State Model

### STUDIO Section

#### S1: Content Page (`/studio/content`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | `<SkeletonTable rows={5} />` | N/A |
| Empty | 0 sources | `<EmptyKnowledge onAdd={...} />` | "No knowledge sources yet" |
| Error | API failure | `<ErrorState onRetry={...} />` | "Failed to load sources" |
| Retry | User clicks | Shows loading then retries | N/A |
| Success | Data received | Source list table | N/A |

**Data Fetch:**
```typescript
// Primary data
GET /sources/{twin_id}

// Secondary data (can fail gracefully)
GET /cognitive/profile/{twin_id}
```
Uploads auto-index on completion; processing transitions to ready automatically.

**Error Handling:**
- Network error → Show retry with correlation ID
- 401 → Redirect to login
- 404 → Show "Twin not found" with link to dashboard
- 500 → Show retry with correlation ID

---

#### S2: Identity Page (`/studio/identity`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | Form skeleton | N/A |
| Empty | N/A (always has twin) | N/A | N/A |
| Error | Load failure | Full-page error | "Failed to load settings" |
| Retry | User clicks | Reloads page | N/A |
| Success | Data received | Form with values | N/A |
| Saving | Form submit | Button spinner + disabled | "Saving..." |
| Save Error | API failure | Toast error | "Failed to save changes" |
| Save Success | API success | Toast success | "Settings saved" |

**Data Fetch:**
```typescript
GET /twins/{twin_id}
```

**Form States:**
- Pristine → Save button disabled
- Dirty → Save button enabled
- Saving → Button shows spinner
- Error → Toast with retry option

---

#### S3: Roles Page (`/studio/roles`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | `<SkeletonCard />` x 3 | N/A |
| Empty | 0 roles | Custom empty state | "Create your first role" |
| Error | API failure | `<ErrorState />` | "Failed to load roles" |
| Success | Data received | Role cards | N/A |

**Note:** Roles is a new feature. Backend endpoint TBD.

---

#### S4: Quality Page (`/studio/quality`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | `<SkeletonChat />` | N/A |
| Empty | No messages | Welcome message | "Ask a test question" |
| Error | Chat failure | Message with retry | "Message failed to send" |
| Streaming | Response in progress | Typing indicator | Partial message |
| Success | Response complete | Full message | N/A |

**Special States:**
- Verification running → Badge shows "Verifying..."
- Low confidence → Warning badge on message
- No context found → Alert banner

---

### LAUNCH Section

#### L1: Share Link Page (`/launch/share`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | Skeleton box | N/A |
| No Link | Link not generated | Generate button | "Generate your share link" |
| Error | API failure | `<ErrorState />` | "Failed to load share link" |
| Success | Link exists | Link display with copy | N/A |
| Copying | Copy clicked | Toast | "Link copied!" |
| Regenerating | Regenerate clicked | Button spinner | "Regenerating..." |

---

#### L2: Website Embed Page (`/launch/embed`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | Code skeleton | N/A |
| Error | API failure | `<ErrorState />` | "Failed to load embed code" |
| Success | Data received | Code block + preview | N/A |
| Copying | Copy clicked | Toast | "Code copied!" |
| Domain Added | Domain submitted | Toast | "Domain added" |
| Domain Removed | Domain deleted | Toast | "Domain removed" |

---

#### L3: Branding Page (`/launch/brand`)

Same as Identity Page state model (form-based).

---

### OPERATE Section

#### O1: Conversations Page (`/operate/conversations`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | `<SkeletonTable rows={10} />` | N/A |
| Empty | 0 conversations | `<EmptyConversations />` | "No conversations yet" |
| Error | API failure | `<ErrorState />` | "Failed to load conversations" |
| Success | Data received | Conversation list | N/A |
| Loading More | Scroll | Spinner at bottom | N/A |
| Filter Applied | Filter change | Loading then list | N/A |

**Pagination:**
- Initial load: 20 items
- Load more on scroll
- Show "No more conversations" at end

---

#### O2: Audience Page (`/operate/audience`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | `<SkeletonStats count={3} />` + `<SkeletonTable />` | N/A |
| Empty | 0 visitors | Custom empty | "No visitors yet" |
| Error | API failure | `<ErrorState />` | "Failed to load audience data" |
| Success | Data received | Stats + visitor list | N/A |

---

#### O3: Analytics Page (`/operate/analytics`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Loading | Page mount | `<SkeletonStats count={3} />` + Chart skeleton | N/A |
| Empty | No data for period | Empty chart | "No data for this period" |
| Error | API failure | `<ErrorState />` | "Failed to load analytics" |
| Success | Data received | Stats + charts | N/A |
| Period Change | Dropdown | Loading then update | N/A |

---

### Public Pages

#### Share Page (`/share/[twin_id]/[token]`)

| State | Trigger | UI Component | Message |
|-------|---------|--------------|---------|
| Validating | Page mount | Full-screen spinner | "Connecting..." |
| Invalid Token | Validation fails | Full-page error | "This link is not valid" |
| Expired | Token expired | Full-page error | "This link has expired" |
| Success | Validated | Chat interface | N/A |
| Sending | Message sent | Typing indicator | N/A |
| Error | Message fails | Inline error | "Failed to send. Retry?" |

---

## Error Display Standards

### Error Message Format

```typescript
interface ErrorDisplay {
  title: string;          // "Something went wrong"
  description: string;    // "We couldn't load your sources."
  correlationId?: string; // "Ref: abc-123-def"
  actions: {
    primary: {
      label: string;      // "Try Again"
      action: () => void;
    };
    secondary?: {
      label: string;      // "Contact Support"
      href: string;
    };
  };
}
```

### Correlation ID Display

For enterprise-grade observability, all errors should display correlation ID:

```tsx
<ErrorState
  title="Failed to load sources"
  description="We encountered an error fetching your knowledge sources."
  correlationId={error.correlationId}
  onRetry={refetch}
/>
```

Display format:
```
┌────────────────────────────────────────┐
│  ⚠️  Failed to load sources           │
│                                        │
│  We encountered an error fetching      │
│  your knowledge sources.               │
│                                        │
│  [Try Again]                           │
│                                        │
│  Ref: abc-123-def-456                  │
│  (Copy reference for support)          │
└────────────────────────────────────────┘
```

---

## Loading States

### Skeleton Presets (Already Available)

| Preset | Use Case |
|--------|----------|
| `<SkeletonText lines={3} />` | Paragraphs, descriptions |
| `<SkeletonAvatar size="lg" />` | Profile images |
| `<SkeletonCard />` | Content cards |
| `<SkeletonTable rows={5} cols={4} />` | Data tables |
| `<SkeletonStats count={4} />` | Metric displays |
| `<SkeletonChat messages={4} />` | Chat interfaces |

### Loading Best Practices

1. **Match layout** - Skeleton should match success state layout
2. **Progressive loading** - Load header first, then content
3. **Minimum duration** - Show skeleton for at least 200ms to avoid flash
4. **Staggered animation** - Shimmer animation should flow directionally

---

## Empty States

### Standard Empty State Copy

| Page | Title | Description | Action |
|------|-------|-------------|--------|
| Content | "No knowledge sources yet" | "Add documents, URLs, or interview recordings" | "Add Your First Source" |
| Roles | "No roles defined" | "Create roles to customize responses for different contexts" | "Create First Role" |
| Conversations | "No conversations yet" | "Share your expert clone to start conversations" | "Go to Share" |
| Audience | "No visitors yet" | "Your audience will appear here once people start chatting" | "View Share Link" |
| Analytics | "No data yet" | "Analytics will appear after your first conversation" | N/A |

---

## State Management Recommendations

### Option 1: React Query (Recommended)

```typescript
import { useQuery } from '@tanstack/react-query';

function ContentPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['sources', twinId],
    queryFn: () => fetchSources(twinId),
  });

  if (isLoading) return <SkeletonTable />;
  if (isError) return <ErrorState error={error} onRetry={refetch} />;
  if (!data?.length) return <EmptyKnowledge />;
  return <SourceList sources={data} />;
}
```

**Pros:**
- Automatic caching
- Background refetching
- Error retry logic built-in
- DevTools for debugging

### Option 2: Custom Hook

```typescript
function useDataState<T>(fetcher: () => Promise<T>) {
  const [state, setState] = useState<PageState<T>>({
    status: 'loading',
    data: null,
    error: null,
    lastUpdated: null,
  });

  // ... implementation
}
```

---

## Implementation Priority

### Phase 1: Foundation
1. Create unified `ErrorState` component with correlation ID
2. Update `EmptyState` with consistent copy
3. Add loading minimum duration utility

### Phase 2: Critical Pages
1. `/studio/content` - Full state model
2. `/studio/quality` - Chat states
3. `/launch/share` - Share states

### Phase 3: Remaining Pages
1. All OPERATE pages
2. All LAUNCH pages
3. Settings pages

### Phase 4: Polish
1. Consistent skeleton layouts
2. Animation timing
3. Accessibility testing
