# Frontend QA Checklist

**Last Updated:** 2026-02-04  
**Product:** Clone-for-Experts (Web-Only)  
**Status:** PLAN ONLY

---

## Overview

This document provides comprehensive QA procedures for the Clone-for-Experts frontend restructure. It covers:

1. Manual QA Checklist
2. UI Test Plan (Playwright)
3. Proof Path Walkthrough

---

## 1. Manual QA Checklist

### Pre-Testing Setup

- [ ] Local dev server running (`npm run dev`)
- [ ] Backend server running (localhost:8000 or production)
- [ ] Test account created
- [ ] Browser DevTools open (Network + Console tabs)
- [ ] Correlation ID logging enabled

---

### A. Authentication Flow

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| A1 | Signup | 1. Go to /auth/signup<br>2. Enter email/password<br>3. Submit | Account created, redirect to onboarding | |
| A2 | Login | 1. Go to /auth/login<br>2. Enter credentials<br>3. Submit | Logged in, redirect to /studio | |
| A3 | Logout | 1. Click logout in sidebar | Logged out, redirect to /auth/login | |
| A4 | Protected route | 1. Log out<br>2. Go to /studio/content | Redirect to /auth/login | |
| A5 | Password reset | 1. Go to /auth/forgot-password<br>2. Enter email<br>3. Submit | Email sent confirmation | |
| A6 | OAuth (Google) | 1. Click "Continue with Google"<br>2. Complete OAuth | Logged in, redirect to /studio | |

---

### B. Onboarding Flow

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| B1 | Start wizard | 1. Login as new user | Onboarding wizard appears | |
| B2 | Name expert | 1. Enter name/tagline<br>2. Click Next | Proceed to content step | |
| B3 | Upload document | 1. Drop PDF file<br>2. Wait for processing | File shows "Ready" status | |
| B4 | Add URL | 1. Enter website URL<br>2. Click Add | URL appears in list, processing starts | |
| B5 | Set personality | 1. Select tone<br>2. Select response length<br>3. Click Next | Settings saved | |
| B6 | Test preview | 1. Type test question<br>2. Wait for response | Response appears with confidence | |
| B7 | Complete wizard | 1. Click Launch | Redirect to /studio/content | |

---

### C. Studio Section

#### C.1 Content Page (`/studio/content`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| C1.1 | Loading state | 1. Refresh page | Skeleton appears, then data loads | |
| C1.2 | Empty state | 1. Delete all sources | EmptyKnowledge component shown | |
| C1.3 | Add document | 1. Click "Add New"<br>2. Upload PDF | Source appears, status "Processing" | |
| C1.4 | Add URL | 1. Paste URL<br>2. Submit | Source appears, status "Processing" | |
| C1.5 | Processing complete | 1. Wait for processing | Status changes to "Ready" | |
| C1.6 | Delete source | 1. Click delete on source<br>2. Confirm | Source removed from list | |
| C1.7 | Error state | 1. Disconnect network<br>2. Refresh | Error state with retry shown | |
| C1.8 | Retry works | 1. Reconnect network<br>2. Click retry | Data loads successfully | |
| C1.9 | Knowledge profile | 1. Observe stats panel | Shows chunks, sources, coverage | |

#### C.2 Identity Page (`/studio/identity`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| C2.1 | Load settings | 1. Go to /studio/identity | Form populated with current values | |
| C2.2 | Change name | 1. Edit name field<br>2. Click Save | Toast: "Settings saved" | |
| C2.3 | Change tone | 1. Select different tone<br>2. Click Save | Tone updated | |
| C2.4 | Change response length | 1. Toggle response length<br>2. Save | Length preference updated | |
| C2.5 | System instructions | 1. Add custom instructions<br>2. Save | Instructions saved | |
| C2.6 | Validation error | 1. Clear required field<br>2. Save | Error message on field | |
| C2.7 | Save error | 1. Disconnect network<br>2. Save | Toast error with retry | |

#### C.3 Roles Page (`/studio/roles`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| C3.1 | Empty state | 1. New account with no roles | Empty state shown | |
| C3.2 | Create role | 1. Click "Add Role"<br>2. Enter name/description<br>3. Save | Role appears in list | |
| C3.3 | Edit role | 1. Click Edit on role<br>2. Modify<br>3. Save | Role updated | |
| C3.4 | Delete role | 1. Click delete<br>2. Confirm | Role removed | |

#### C.4 Quality Page (`/studio/quality`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| C4.1 | Initial state | 1. Go to /studio/quality | Welcome message shown | |
| C4.2 | Send message | 1. Type question<br>2. Press Enter | Message sent, typing indicator | |
| C4.3 | Receive response | 1. Wait for response | Response with confidence score | |
| C4.4 | Knowledge context | 1. Observe context panel | Relevant sources shown | |
| C4.5 | New session | 1. Click "New Session" | Chat cleared | |
| C4.6 | Streaming partial | 1. Send long question | Response streams in chunks | |
| C4.7 | Low confidence | 1. Ask off-topic question | Warning badge on response | |
| C4.8 | No context | 1. Ask obscure question | Alert: "No relevant sources" | |

---

### D. Launch Section

#### D.1 Share Link Page (`/launch/share`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| D1.1 | No link state | 1. New expert, no link | "Generate Link" button shown | |
| D1.2 | Generate link | 1. Click "Generate Link" | Link displayed with copy button | |
| D1.3 | Copy link | 1. Click "Copy" | Toast: "Link copied!" | |
| D1.4 | QR code | 1. Click "QR Code" | QR code modal appears | |
| D1.5 | Regenerate | 1. Click "Regenerate"<br>2. Confirm | New link generated, old invalidated | |
| D1.6 | Visit link | 1. Open link in incognito | Public chat loads | |

#### D.2 Website Embed Page (`/launch/embed`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| D2.1 | Load embed code | 1. Go to /launch/embed | Embed code displayed | |
| D2.2 | Copy code | 1. Click "Copy Code" | Toast: "Code copied!" | |
| D2.3 | Add domain | 1. Enter domain<br>2. Click "Add" | Domain appears in list | |
| D2.4 | Remove domain | 1. Click X on domain | Domain removed | |
| D2.5 | Preview widget | 1. Observe preview | Widget renders correctly | |
| D2.6 | Test embed | 1. Paste code in test HTML<br>2. Open in browser | Widget loads and works | |

#### D.3 Branding Page (`/launch/brand`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| D3.1 | Load settings | 1. Go to /launch/brand | Current branding shown | |
| D3.2 | Change color | 1. Pick new color<br>2. Save | Widget updates color | |
| D3.3 | Change position | 1. Toggle position<br>2. Save | Widget moves position | |
| D3.4 | Custom greeting | 1. Enter greeting<br>2. Save | Greeting appears in widget | |
| D3.5 | Live preview | 1. Make changes | Preview updates in real-time | |

---

### E. Operate Section

#### E.1 Conversations Page (`/operate/conversations`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| E1.1 | Empty state | 1. New expert, no conversations | Empty state shown | |
| E1.2 | List conversations | 1. After visitor chats | Conversations appear in list | |
| E1.3 | Filter by date | 1. Select date filter | List updates | |
| E1.4 | View conversation | 1. Click conversation | Messages displayed | |
| E1.5 | Pagination | 1. Scroll to bottom | "Load More" or new items load | |
| E1.6 | Export | 1. Click "Export" | CSV downloads | |

#### E.2 Audience Page (`/operate/audience`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| E2.1 | Empty state | 1. New expert | Empty state shown | |
| E2.2 | Stats display | 1. After visitors | Stats cards populated | |
| E2.3 | Visitor list | 1. Observe list | Sessions shown | |

#### E.3 Analytics Page (`/operate/analytics`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| E3.1 | Empty state | 1. New expert | "No data yet" message | |
| E3.2 | Stats cards | 1. After activity | Metrics displayed | |
| E3.3 | Change period | 1. Select "30 Days" | Data updates | |
| E3.4 | Top questions | 1. Observe list | Questions ranked by frequency | |
| E3.5 | Export | 1. Click "Export" | Report downloads | |

---

### F. Public Chat (`/share/[twin_id]/[token]`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| F1 | Valid link | 1. Open valid share link | Chat loads, greeting shown | |
| F2 | Invalid token | 1. Open with wrong token | "Invalid link" error | |
| F3 | Expired link | 1. Open regenerated link | "Link expired" error | |
| F4 | Send message | 1. Type message<br>2. Send | Response received | |
| F5 | Mobile responsive | 1. Open on mobile | Layout adapts correctly | |
| F6 | Error handling | 1. Disconnect network<br>2. Send message | Error with retry option | |
| F7 | Retry works | 1. Reconnect<br>2. Click retry | Message sends | |

---

### G. Settings Page (`/settings`)

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| G1 | Load profile | 1. Go to /settings | Profile info displayed | |
| G2 | Update profile | 1. Change name<br>2. Save | Profile updated | |
| G3 | Change password | 1. Enter current/new password<br>2. Save | Password changed | |
| G4 | Theme toggle | 1. Toggle dark/light mode | Theme changes | |
| G5 | Delete expert | 1. Click delete in Danger Zone<br>2. Confirm | Expert deleted, redirect | |

---

### H. Cross-Cutting Concerns

| # | Test Case | Steps | Expected Result | Pass/Fail |
|---|-----------|-------|-----------------|-----------|
| H1 | Responsive mobile | 1. Resize to mobile | All pages render correctly | |
| H2 | Responsive tablet | 1. Resize to tablet | Layout adapts | |
| H3 | Dark mode | 1. Toggle theme | All pages have dark styles | |
| H4 | Keyboard navigation | 1. Tab through page | Focus visible, logical order | |
| H5 | Skip navigation | 1. Tab on page load | "Skip to content" visible | |
| H6 | Error boundary | 1. Trigger JS error | Error boundary catches, shows recovery | |
| H7 | Loading performance | 1. Check Lighthouse | Performance score > 70 | |
| H8 | Accessibility | 1. Run axe DevTools | No critical violations | |

---

## 2. UI Test Plan (Playwright)

### Test File Structure

```
frontend/tests/
├── auth/
│   ├── login.spec.ts
│   ├── signup.spec.ts
│   └── logout.spec.ts
├── studio/
│   ├── content.spec.ts
│   ├── identity.spec.ts
│   ├── roles.spec.ts
│   └── quality.spec.ts
├── launch/
│   ├── share.spec.ts
│   ├── embed.spec.ts
│   └── brand.spec.ts
├── operate/
│   ├── conversations.spec.ts
│   ├── audience.spec.ts
│   └── analytics.spec.ts
├── public/
│   └── share-chat.spec.ts
└── e2e/
    └── full-flow.spec.ts
```

### Example Test: Content Page

```typescript
// frontend/tests/studio/content.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Content Page', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/auth/login');
    await page.fill('[data-testid="email"]', 'test@example.com');
    await page.fill('[data-testid="password"]', 'password123');
    await page.click('[data-testid="submit"]');
    await page.waitForURL('/studio/**');
  });

  test('shows empty state for new expert', async ({ page }) => {
    await page.goto('/studio/content');
    await expect(page.locator('[data-testid="empty-knowledge"]')).toBeVisible();
  });

  test('can upload document', async ({ page }) => {
    await page.goto('/studio/content');
    
    // Upload file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('tests/fixtures/sample.pdf');
    
    // Wait for upload
    await expect(page.locator('[data-testid="source-item"]')).toBeVisible();
    await expect(page.locator('text=Processing')).toBeVisible();
  });

  test('shows error state on network failure', async ({ page }) => {
    await page.route('**/sources/**', route => route.abort());
    await page.goto('/studio/content');
    
    await expect(page.locator('[data-testid="error-state"]')).toBeVisible();
    await expect(page.locator('text=Try Again')).toBeVisible();
  });
});
```

### Example Test: Full E2E Flow

```typescript
// frontend/tests/e2e/full-flow.spec.ts
import { test, expect } from '@playwright/test';

test('complete expert creation and launch flow', async ({ page }) => {
  // 1. Signup
  await page.goto('/auth/signup');
  await page.fill('[data-testid="email"]', `test-${Date.now()}@example.com`);
  await page.fill('[data-testid="password"]', 'SecurePass123!');
  await page.click('[data-testid="submit"]');
  
  // Wait for onboarding
  await page.waitForURL('/onboarding');
  
  // 2. Complete onboarding
  await page.fill('[data-testid="expert-name"]', 'Test Expert');
  await page.click('[data-testid="next"]');
  
  // Upload content
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles('tests/fixtures/sample.pdf');
  await page.waitForSelector('[data-testid="source-ready"]');
  await page.click('[data-testid="next"]');
  
  // Set personality
  await page.click('[data-testid="tone-professional"]');
  await page.click('[data-testid="next"]');
  
  // Preview and launch
  await page.fill('[data-testid="test-question"]', 'What is this about?');
  await page.click('[data-testid="send"]');
  await page.waitForSelector('[data-testid="response"]');
  await page.click('[data-testid="launch"]');
  
  // 3. Verify in studio
  await page.waitForURL('/studio/content');
  await expect(page.locator('[data-testid="source-item"]')).toBeVisible();
  
  // 4. Generate share link
  await page.goto('/launch/share');
  await page.click('[data-testid="generate-link"]');
  const shareLink = await page.locator('[data-testid="share-url"]').textContent();
  
  // 5. Test public chat
  await page.goto(shareLink);
  await expect(page.locator('[data-testid="chat-interface"]')).toBeVisible();
  await page.fill('[data-testid="chat-input"]', 'Hello');
  await page.click('[data-testid="send"]');
  await expect(page.locator('[data-testid="response"]')).toBeVisible();
});
```

### Test Configuration

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  retries: 2,
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
    { name: 'webkit', use: { browserName: 'webkit' } },
    { name: 'mobile', use: { ...devices['iPhone 12'] } },
  ],
});
```

---

## 3. Proof Path Walkthrough

This walkthrough provides step-by-step verification that the restructured application works end-to-end.

### Prerequisites
- [ ] Frontend running on localhost:3000
- [ ] Backend running on localhost:8000
- [ ] Fresh test database (or specific test tenant)

### Proof Path Steps

#### Step 1: Login (Expected: 30 seconds)

1. Open http://localhost:3000
2. Click "Sign In"
3. Enter test credentials
4. Verify redirect to `/studio`
5. Verify sidebar shows Studio/Launch/Operate sections

**Screenshot checkpoint:** Dashboard loads with sidebar

---

#### Step 2: Add Content (Expected: 2 minutes)

1. Navigate to `/studio/content`
2. Observe empty state message
3. Click "Add Your First Source"
4. Upload `test-document.pdf`
5. Observer processing status
6. Wait for "Ready" status
7. Verify knowledge profile updates

**Screenshot checkpoint:** Source shows "Ready" with chunk count

---

#### Step 3: Configure Identity (Expected: 1 minute)

1. Navigate to `/studio/identity`
2. Change tone to "Friendly"
3. Set response length to "Balanced"
4. Add custom instruction: "Always be helpful"
5. Click Save
6. Verify toast: "Settings saved"

**Screenshot checkpoint:** Settings form with saved values

---

#### Step 4: Test Quality (Expected: 2 minutes)

1. Navigate to `/studio/quality`
2. Type: "What is in the document I uploaded?"
3. Press Enter
4. Observe typing indicator
5. Verify response appears with confidence score
6. Verify context panel shows relevant source
7. Click "New Session"
8. Verify chat is cleared

**Screenshot checkpoint:** Response with confidence badge

---

#### Step 5: Generate Share Link (Expected: 30 seconds)

1. Navigate to `/launch/share`
2. Click "Generate Link"
3. Verify link appears
4. Click "Copy"
5. Verify toast: "Link copied!"
6. Note the link for Step 7

**Screenshot checkpoint:** Share link visible with copy button

---

#### Step 6: Get Embed Code (Expected: 30 seconds)

1. Navigate to `/launch/embed`
2. Observe embed code
3. Add "localhost:3000" to allowed domains
4. Click "Copy Code"
5. Verify toast confirmation

**Screenshot checkpoint:** Embed code with allowed domains

---

#### Step 7: Test Public Chat (Expected: 1 minute)

1. Open new incognito window
2. Paste share link from Step 5
3. Verify chat loads
4. Type: "Hello"
5. Press Enter
6. Verify response appears
7. Observe no login required

**Screenshot checkpoint:** Public chat working without auth

---

#### Step 8: Check Conversations (Expected: 30 seconds)

1. Return to main window (logged in)
2. Navigate to `/operate/conversations`
3. Verify conversation from Step 7 appears
4. Click to view messages
5. Verify full conversation visible

**Screenshot checkpoint:** Conversation list with visitor chat

---

#### Step 9: View Analytics (Expected: 30 seconds)

1. Navigate to `/operate/analytics`
2. Verify message count increased
3. Verify stats cards populated
4. Change period to "7 Days"
5. Verify data updates

**Screenshot checkpoint:** Analytics with real data

---

#### Step 10: Settings and Cleanup (Expected: 1 minute)

1. Navigate to `/settings`
2. Toggle dark mode
3. Verify theme changes
4. Navigate to identity, check dark mode styles
5. Return to settings
6. (Optional) Delete expert to clean up

**Screenshot checkpoint:** Dark mode across pages

---

### Expected Total Time: ~10 minutes

### Proof Artifacts to Capture

1. [ ] Screenshot: Studio content page with sources
2. [ ] Screenshot: Quality chat with response
3. [ ] Screenshot: Share link generated
4. [ ] Screenshot: Public chat working
5. [ ] Screenshot: Conversation in operate section
6. [ ] Screenshot: Analytics with data
7. [ ] Video: Full flow recording (optional)

---

## Test Data Requirements

### Fixtures

```
frontend/tests/fixtures/
├── sample.pdf          # Simple PDF for upload testing
├── sample.docx         # DOCX for format testing
├── sample.txt          # Plain text file
└── test-accounts.json  # Test credentials
```

### Test Accounts

| Email | Password | State |
|-------|----------|-------|
| new@test.com | Test123! | Fresh account |
| expert@test.com | Test123! | Has content and conversations |
| empty@test.com | Test123! | Account with no expert |

---

## Pass/Fail Criteria

### MVP Release Gate

- [ ] All A (Auth) tests pass
- [ ] All B (Onboarding) tests pass
- [ ] All C (Studio) tests pass
- [ ] All D (Launch) tests pass
- [ ] All F (Public Chat) tests pass
- [ ] Proof path completes in < 15 minutes
- [ ] No critical accessibility violations
- [ ] Mobile responsive on all pages

### Quality Gate

- [ ] All E (Operate) tests pass
- [ ] All G (Settings) tests pass
- [ ] All H (Cross-cutting) tests pass
- [ ] Lighthouse performance > 70
- [ ] E2E test suite passes
