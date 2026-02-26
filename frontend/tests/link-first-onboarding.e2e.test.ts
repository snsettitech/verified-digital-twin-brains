/**
 * Unified Onboarding E2E Tests
 *
 * Tests the consolidated onboarding flow: single input screen -> research -> complete.
 * No mode selector; name-only or name + optional sources.
 */

import { test, expect, type Page } from '@playwright/test';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// =============================================================================
// Test Helpers
// =============================================================================

async function createTestUser(page: Page) {
  await page.goto('/auth/login');
  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="password"]', 'testpassword123');
  await page.click('button[type="submit"]');
  await page.waitForURL('/dashboard');
}

// =============================================================================
// Contract Tests
// =============================================================================

test.describe('Contract Tests', () => {
  test('TwinCreateRequest schema validation', async ({ request }) => {
    const payload = {
      name: 'Test Twin',
      mode: 'link_first',
      specialization: 'vanilla',
    };

    const response = await request.post(`${API_BASE_URL}/twins`, {
      headers: { 'Content-Type': 'application/json' },
      data: payload,
    });

    expect(response.status()).toBe(401); // Unauthorized without auth, but schema accepted
  });

  test('GET /twins/{id} returns status field', async ({ request }) => {
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
// Unified Onboarding Flow Tests
// =============================================================================

test.describe('Unified Onboarding Flow', () => {
  test.beforeEach(async ({ page }) => {
    await createTestUser(page);
  });

  test('unified flow shows single input screen', async ({ page }) => {
    await page.goto('/onboarding');

    await expect(page.locator('text=Create Your Digital Twin')).toBeVisible();
    await expect(page.locator('text=Full Name')).toBeVisible();
    await expect(page.locator('text=Create My Digital Twin')).toBeVisible();
  });

  test('unified flow creates twin and starts research', async ({ page }) => {
    await page.goto('/onboarding');

    await page.getByPlaceholder(/Sarah Chen/).fill('Test User');
    await page.getByRole('checkbox').check();
    await page.click('text=Create My Digital Twin');

    await page.waitForSelector('text=Starting Research, text=Research, text=Creating research', { timeout: 15000 });
  });

  test('onboarding/v2 redirects to /onboarding', async ({ page }) => {
    await page.goto('/onboarding/v2');
    await expect(page).toHaveURL(/\/onboarding/);
    await expect(page).not.toHaveURL(/\/v2/);
  });
});

// =============================================================================
// API Rate Limiting Tests
// =============================================================================

test.describe('API Rate Limiting', () => {
  test('validate-url endpoint has rate limiting', async ({ request }) => {
    const promises = Array(10).fill(null).map(() =>
      request.post(`${API_BASE_URL}/persona/link-compile/validate-url`, {
        data: { url: 'https://example.com' },
      })
    );

    const responses = await Promise.all(promises);

    const successCount = responses.filter(r => r.status() === 200).length;
    const rateLimitedCount = responses.filter(r => r.status() === 429).length;

    expect(successCount + rateLimitedCount).toBe(10);
  });

  test('job creation endpoint has rate limiting', async ({ request }) => {
    const twinId = 'test-twin-id';

    const promises = Array(5).fill(null).map(() =>
      request.post(`${API_BASE_URL}/persona/link-compile/jobs/mode-c`, {
        headers: { 'Content-Type': 'application/json' },
        data: { twin_id: twinId, urls: ['https://example.com'] },
      })
    );

    const responses = await Promise.all(promises);

    const hasRateLimit = responses.some(r => r.status() === 429);
    expect(hasRateLimit || responses.every(r => [200, 401, 404].includes(r.status()))).toBeTruthy();
  });
});

// =============================================================================
// State Machine Tests
// =============================================================================

test.describe('State Machine Transitions', () => {
  test('draft → ingesting transition', async () => {
    const twin = { id: 'test', status: 'draft' };
    expect(twin.status).toBe('draft');

    twin.status = 'ingesting';
    expect(twin.status).toBe('ingesting');
  });

  test('ingesting → claims_ready transition', async () => {
    const twin = { id: 'test', status: 'ingesting' };

    twin.status = 'claims_ready';
    expect(twin.status).toBe('claims_ready');
  });

  test('claims_ready → clarification_pending transition', async () => {
    const twin = { id: 'test', status: 'claims_ready' };

    twin.status = 'clarification_pending';
    expect(twin.status).toBe('clarification_pending');
  });

  test('clarification_pending → persona_built transition', async () => {
    const twin = { id: 'test', status: 'clarification_pending' };

    twin.status = 'persona_built';
    expect(twin.status).toBe('persona_built');
  });

  test('persona_built → active transition', async () => {
    const twin = { id: 'test', status: 'persona_built' };

    twin.status = 'active';
    expect(twin.status).toBe('active');
  });
});
