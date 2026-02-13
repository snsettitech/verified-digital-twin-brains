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

test.describe('Teaching UX', () => {
  test('owner can submit correction from chat and see applied status', async ({ page }) => {
    const trainingState = createTrainingHarnessState();
    await registerTrainingModuleRoutes(page, trainingState);

    const correctionBodies: Array<Record<string, unknown>> = [];
    await page.route(`${BACKEND_GLOB}/twins/e2e-twin/owner-corrections`, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: CORS_HEADERS, body: '' });
        return;
      }
      const body = (route.request().postDataJSON() || {}) as Record<string, unknown>;
      correctionBodies.push(body);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: CORS_HEADERS,
        body: json({
          status: 'applied',
          owner_memory_id: 'mem-e2e-1',
          verified_qna_id: 'vq-e2e-1',
        }),
      });
    });

    await page.goto('/dashboard/simulator');

    const input = page.locator('textarea[aria-label="Chat message input"]');
    await input.fill('How should I evaluate founder risk?');
    await input.press('Enter');
    await expect(page.getByText('Owner chat answer.')).toBeVisible();

    const correctButtons = page.getByRole('button', { name: 'Correct' });
    await correctButtons.last().click({ force: true });

    const correctionInput = page.getByPlaceholder('Enter the corrected answer.');
    await correctionInput.fill('I evaluate founder risk by integrity, learning velocity, and execution cadence.');
    await page.getByRole('button', { name: 'Apply' }).click();

    await expect(page.getByText('Applied')).toBeVisible();
    await expect.poll(() => correctionBodies.length).toBe(1);

    const payload = correctionBodies[0];
    expect(payload.question).toBe('How should I evaluate founder risk?');
    expect(payload.corrected_answer).toBe(
      'I evaluate founder risk by integrity, learning velocity, and execution cadence.',
    );
    expect(payload.memory_type).toBe('belief');
    expect(payload.create_verified_qna_entry).toBe(true);
  });

  test('public share chat does not expose owner correction controls', async ({ page }) => {
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: CORS_HEADERS,
        body: json({
          response: 'Public response only.',
          citations: [],
          confidence_score: 0.8,
        }),
      });
    });

    await page.goto('/share/e2e-twin/token-e2e');
    const input = page.getByPlaceholder('Type your message...');
    await input.fill('Public chat question');
    await input.press('Enter');

    await expect(page.getByText('Public response only.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Correct' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Remember' })).toHaveCount(0);
  });
});
