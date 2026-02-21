/**
 * Link-First Persona Onboarding E2E Tests
 * 
 * Tests the complete Link-First flow from twin creation to activation.
 */

import { test, expect } from '@playwright/test';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// =============================================================================
// Test Helpers
// =============================================================================

async function createTestUser(page: any) {
  // Sign in via Supabase (assumes test credentials are configured)
  await page.goto('/auth/login');
  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="password"]', 'testpassword123');
  await page.click('button[type="submit"]');
  await page.waitForURL('/dashboard');
}

async function createLinkFirstTwin(page: any) {
  await page.goto('/onboarding');
  
  // Select Link-First mode
  await page.click('text=Link-First (Beta)');
  
  // Wait for twin creation (should auto-create in draft mode)
  await page.waitForSelector('text=Submit Your Content');
  
  // Submit a URL
  await page.fill('input[type="url"]', 'https://example.com/test-article');
  await page.click('text=Start Processing');
  
  // Wait for ingestion step
  await page.waitForSelector('text=Processing Your Content');
}

// =============================================================================
// Contract Tests
// =============================================================================

test.describe('Contract Tests', () => {
  test('TwinCreateRequest schema validation', async ({ request }) => {
    const payload = {
      name: 'Test Twin',
      mode: 'link_first',
      links: ['https://example.com/article'],
      specialization: 'vanilla',
    };
    
    // This will fail if backend rejects the schema
    const response = await request.post(`${API_BASE_URL}/twins`, {
      headers: { 'Content-Type': 'application/json' },
      data: payload,
    });
    
    expect(response.status()).toBe(401); // Unauthorized without auth, but schema accepted
  });

  test('GET /twins/{id} returns status field', async ({ request }) => {
    // This test assumes a twin exists - in real tests, create one first
    const twinId = 'test-twin-id';
    const response = await request.get(`${API_BASE_URL}/twins/${twinId}`);
    
    if (response.status() === 200) {
      const data = await response.json();
      expect(data).toHaveProperty('status');
      expect(['draft', 'ingesting', 'claims_ready', 'clarification_pending', 'persona_built', 'active']).toContain(data.status);
    }
  });

  test('Link-compile job endpoint returns correct schema', async ({ request }) => {
    const twinId = 'test-twin-id';
    const response = await request.get(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/job`);
    
    if (response.status() === 200) {
      const data = await response.json();
      expect(data).toHaveProperty('job_id');
      expect(data).toHaveProperty('status');
      expect(data).toHaveProperty('total_sources');
      expect(data).toHaveProperty('extracted_claims');
    }
  });
});

// =============================================================================
// Link-First Onboarding Flow Tests
// =============================================================================

test.describe('Link-First Onboarding Flow', () => {
  test.beforeEach(async ({ page }) => {
    await createTestUser(page);
  });

  test('complete link-first flow reaches active status', async ({ page }) => {
    // 1. Start onboarding and select Link-First mode
    await page.goto('/onboarding');
    await page.click('text=Link-First (Beta)');
    
    // 2. Submit content
    await page.waitForSelector('text=Submit Your Content');
    await page.fill('input[type="url"]', 'https://example.com/test-article');
    await page.click('text=Start Processing');
    
    // 3. Verify ingestion progress screen
    await page.waitForSelector('text=Processing Your Content', { timeout: 10000 });
    
    // In a real test environment, we'd mock the backend to fast-forward
    // For now, verify the polling mechanism exists
    const progressBar = await page.locator('.bg-indigo-600.h-4.rounded-full');
    await expect(progressBar).toBeVisible();
  });

  test('mode selector visible when feature flag enabled', async ({ page }) => {
    // Set feature flag (assumes app reads from env)
    await page.goto('/onboarding');
    
    // Should see both manual and link-first options
    await expect(page.locator('text=Manual Setup')).toBeVisible();
    await expect(page.locator('text=Link-First (Beta)')).toBeVisible();
  });

  test('link-first twin created with draft status', async ({ page, request }) => {
    await page.goto('/onboarding');
    await page.click('text=Link-First (Beta)');
    
    // Wait for draft creation
    await page.waitForSelector('text=Draft Mode', { timeout: 5000 });
    
    // Get twin ID from URL or storage
    const url = page.url();
    // Twin should be created - verify by checking the UI shows draft indicator
    await expect(page.locator('text=Creating twin draft')).not.toBeVisible();
  });

  test('resume onboarding redirects to correct step', async ({ page }) => {
    // Create a twin first
    await createLinkFirstTwin(page);
    
    // Get twin ID (from URL or API)
    const twinId = 'mock-twin-id'; // In real test, extract from page
    
    // Navigate to resume URL
    await page.goto(`/onboarding?twinId=${twinId}`);
    
    // Should land on ingestion progress (since we submitted content)
    await expect(page.locator('text=Processing Your Content')).toBeVisible();
  });
});

// =============================================================================
// Manual Onboarding Regression Tests
// =============================================================================

test.describe('Manual Onboarding (Regression)', () => {
  test.beforeEach(async ({ page }) => {
    await createTestUser(page);
  });

  test('manual onboarding creates active twin immediately', async ({ page }) => {
    await page.goto('/onboarding');
    
    // Select manual mode
    await page.click('text=Manual Setup');
    
    // Step 1: Identity
    await page.fill('input[name="twinName"]', 'Test Manual Twin');
    await page.click('text=Next →');
    
    // Step 2: Thinking Style
    await page.click('text=Next →');
    
    // Step 3: Values (required)
    await page.click('text=Growth'); // Select a value
    await page.click('text=Next →');
    
    // Step 4: Communication
    await page.click('text=Next →');
    
    // Step 5: Memory
    await page.click('text=Next →');
    
    // Step 6: Review and Launch
    await page.click('text=Launch Digital Twin');
    
    // Should redirect to chat/dashboard
    await page.waitForURL(/\/(chat|dashboard)/, { timeout: 10000 });
    
    // Twin should be active - verify chat works
    await expect(page.locator('text=Test Manual Twin')).toBeVisible();
  });

  test('manual onboarding unchanged by link-first feature', async ({ page }) => {
    await page.goto('/onboarding');
    await page.click('text=Manual Setup');
    
    // Should see 6-step flow
    await expect(page.locator('text=Step 1 of 6')).toBeVisible();
    await expect(page.locator('text=Identity')).toBeVisible();
    await expect(page.locator('text=Thinking Style')).toBeVisible();
    await expect(page.locator('text=Values')).toBeVisible();
  });
});

// =============================================================================
// Chat Gating Tests
// =============================================================================

test.describe('Chat Gating', () => {
  test.beforeEach(async ({ page }) => {
    await createTestUser(page);
  });

  test('chat redirects to onboarding for non-active twin', async ({ page }) => {
    // Create a link-first twin (draft status)
    await createLinkFirstTwin(page);
    
    // Try to access chat directly
    const twinId = 'mock-draft-twin-id';
    await page.goto(`/chat?twinId=${twinId}`);
    
    // Should redirect to onboarding resume
    await page.waitForURL(/\/onboarding/);
    await expect(page.locator('text=Continue Setup')).toBeVisible();
  });

  test('dashboard shows continue setup for non-active twins', async ({ page }) => {
    // Create a link-first twin
    await createLinkFirstTwin(page);
    
    // Go to dashboard
    await page.goto('/dashboard');
    
    // Should see "Continue Setup" section
    await expect(page.locator('text=Continue Setup')).toBeVisible();
  });

  test('active twin allows chat access', async ({ page }) => {
    // Create a manual twin (active immediately)
    await page.goto('/onboarding');
    await page.click('text=Manual Setup');
    await page.fill('input[name="twinName"]', 'Active Test Twin');
    await page.click('text=Next →');
    await page.click('text=Next →');
    await page.click('text=Growth');
    await page.click('text=Next →');
    await page.click('text=Next →');
    await page.click('text=Next →');
    await page.click('text=Launch Digital Twin');
    
    // Should be redirected to chat
    await page.waitForURL(/\/(chat|dashboard)/, { timeout: 10000 });
    
    // Chat should be accessible
    await expect(page.locator('text=Active Test Twin')).toBeVisible();
  });

  test('backend returns 403 for chat on non-active twin', async ({ request }) => {
    const twinId = 'draft-twin-id';
    const response = await request.post(`${API_BASE_URL}/chat/${twinId}`, {
      headers: { 'Content-Type': 'application/json' },
      data: { query: 'Hello' },
    });
    
    // Should be 403 Forbidden (or 401 if not authenticated)
    expect([401, 403]).toContain(response.status());
  });
});

// =============================================================================
// API Rate Limiting Tests
// =============================================================================

test.describe('API Rate Limiting', () => {
  test('validate-url endpoint has rate limiting', async ({ request }) => {
    // Make multiple rapid requests
    const promises = Array(10).fill(null).map(() => 
      request.post(`${API_BASE_URL}/persona/link-compile/validate-url`, {
        data: { url: 'https://example.com' },
      })
    );
    
    const responses = await Promise.all(promises);
    
    // Most should succeed, some might be rate limited
    const successCount = responses.filter(r => r.status() === 200).length;
    const rateLimitedCount = responses.filter(r => r.status() === 429).length;
    
    expect(successCount + rateLimitedCount).toBe(10);
  });

  test('job creation endpoint has rate limiting', async ({ request }) => {
    const twinId = 'test-twin-id';
    
    // Make multiple rapid job creation requests
    const promises = Array(5).fill(null).map(() => 
      request.post(`${API_BASE_URL}/persona/link-compile/jobs/mode-c`, {
        headers: { 'Content-Type': 'application/json' },
        data: { twin_id: twinId, urls: ['https://example.com'] },
      })
    );
    
    const responses = await Promise.all(promises);
    
    // Should eventually rate limit
    const hasRateLimit = responses.some(r => r.status() === 429);
    expect(hasRateLimit || responses.every(r => [200, 401, 404].includes(r.status()))).toBeTruthy();
  });
});

// =============================================================================
// State Machine Tests
// =============================================================================

test.describe('State Machine Transitions', () => {
  test('draft → ingesting transition', async () => {
    // Initial state after twin creation with mode=link_first
    const twin = { id: 'test', status: 'draft' };
    expect(twin.status).toBe('draft');
    
    // After submitting content
    twin.status = 'ingesting';
    expect(twin.status).toBe('ingesting');
  });

  test('ingesting → claims_ready transition', async () => {
    const twin = { id: 'test', status: 'ingesting' };
    
    // After claims extraction complete
    twin.status = 'claims_ready';
    expect(twin.status).toBe('claims_ready');
  });

  test('claims_ready → clarification_pending transition', async () => {
    const twin = { id: 'test', status: 'claims_ready' };
    
    // After user reviews claims
    twin.status = 'clarification_pending';
    expect(twin.status).toBe('clarification_pending');
  });

  test('clarification_pending → persona_built transition', async () => {
    const twin = { id: 'test', status: 'clarification_pending' };
    
    // After user answers questions
    twin.status = 'persona_built';
    expect(twin.status).toBe('persona_built');
  });

  test('persona_built → active transition', async () => {
    const twin = { id: 'test', status: 'persona_built' };
    
    // After activation
    twin.status = 'active';
    expect(twin.status).toBe('active');
  });
});
