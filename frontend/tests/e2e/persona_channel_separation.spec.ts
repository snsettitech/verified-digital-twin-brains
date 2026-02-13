import { expect, test } from '@playwright/test';

import {
  createTrainingHarnessState,
  registerTrainingModuleRoutes,
} from './helpers/personaHarness';

test.setTimeout(90000);

const BACKEND_GLOB = '**';
const CORS_HEADERS: Record<string, string> = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
  'access-control-allow-headers': 'authorization,content-type,x-correlation-id',
};

function json(obj: unknown): string {
  return JSON.stringify(obj);
}

test.describe('Persona Channel Separation (UI)', () => {
  test('public share traffic is isolated from owner training payload contract', async ({ page }) => {
    const trainingState = createTrainingHarnessState();
    await registerTrainingModuleRoutes(page, trainingState);

    const publicBodies: Array<Record<string, unknown>> = [];

    await page.route(`${BACKEND_GLOB}/public/validate-share/e2e-twin/token-e2e`, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: CORS_HEADERS, body: '' });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: CORS_HEADERS,
        body: json({ twin_name: 'E2E Public Twin' }),
      });
    });

    await page.route(`${BACKEND_GLOB}/public/chat/e2e-twin/token-e2e`, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: CORS_HEADERS, body: '' });
        return;
      }
      const body = (route.request().postDataJSON() || {}) as Record<string, unknown>;
      publicBodies.push(body);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: CORS_HEADERS,
        body: json({
          response: 'Public channel reply.',
          citations: [],
          used_owner_memory: false,
          owner_memory_topics: [],
          confidence_score: 0.92,
        }),
      });
    });

    // Owner training request carries explicit training context.
    await page.goto('/dashboard/simulator');
    await page.getByRole('button', { name: 'Start Training' }).click();

    const ownerInput = page.locator('textarea[aria-label="Chat message input"]');
    await ownerInput.fill('Owner training message');
    await ownerInput.press('Enter');
    await expect(page.getByText('Training context answer.')).toBeVisible();

    await expect.poll(() => trainingState.ownerChatBodies.length).toBe(1);
    expect(trainingState.ownerChatBodies[0].mode).toBe('training');
    expect(trainingState.ownerChatBodies[0].training_session_id).toBe('ts-e2e-1');

    // Public share request must not carry owner-training controls.
    await page.goto('/share/e2e-twin/token-e2e');
    await expect(page.getByRole('heading', { name: 'E2E Public Twin' })).toBeVisible();

    const publicInput = page.getByPlaceholder('Type your message...');
    await publicInput.fill('Public user message');
    await publicInput.press('Enter');
    await expect(page.getByText('Public channel reply.')).toBeVisible();

    await expect(page.getByRole('button', { name: 'Start Training' })).toHaveCount(0);
    await expect.poll(() => publicBodies.length).toBe(1);

    const payload = publicBodies[0];
    expect(payload.message).toBe('Public user message');
    expect(Array.isArray(payload.conversation_history)).toBe(true);
    expect(payload.mode).toBeUndefined();
    expect(payload.training_session_id).toBeUndefined();
    expect(trainingState.ownerChatBodies.length).toBe(1);
  });
});
