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

test.describe('Chat Citations', () => {
  test('owner simulator chat renders citation link and confidence', async ({ page }) => {
    const trainingState = createTrainingHarnessState();
    await registerTrainingModuleRoutes(page, trainingState);

    await page.route(`${BACKEND_GLOB}/chat/e2e-twin`, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: CORS_HEADERS, body: '' });
        return;
      }
      const payload =
        `${json({
          type: 'metadata',
          conversation_id: 'conv-cite-owner',
          citations: ['src-owner-1'],
          citation_details: [
            {
              id: 'src-owner-1',
              filename: 'owner-deck.pdf',
              citation_url: 'https://example.com/owner-deck.pdf',
            },
          ],
          confidence_score: 0.91,
          owner_memory_refs: [],
          owner_memory_topics: [],
        })}\n` +
        `${json({ type: 'content', content: 'Owner citation response.' })}\n` +
        `${json({ type: 'done' })}\n`;

      await route.fulfill({
        status: 200,
        headers: {
          ...CORS_HEADERS,
          'content-type': 'application/x-ndjson',
        },
        body: payload,
      });
    });

    await page.goto('/dashboard/simulator/owner');

    const input = page.locator('textarea[aria-label="Chat message input"]');
    await input.fill('Show me cited answer');
    await input.press('Enter');

    await expect(page.getByText('Owner citation response.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'owner-deck.pdf' })).toBeVisible();
    await expect(page.getByText('Verified: 91%')).toBeVisible();
  });

  test('owner simulator chat parses NDJSON tail without trailing newline', async ({ page }) => {
    const trainingState = createTrainingHarnessState();
    await registerTrainingModuleRoutes(page, trainingState);

    await page.route(`${BACKEND_GLOB}/chat/e2e-twin`, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: CORS_HEADERS, body: '' });
        return;
      }
      const payload =
        `${json({
          type: 'metadata',
          conversation_id: 'conv-tail-owner',
          citations: ['src-tail-1'],
          citation_details: [
            {
              id: 'src-tail-1',
              filename: 'tail-owner.pdf',
              citation_url: 'https://example.com/tail-owner.pdf',
            },
          ],
          confidence_score: 0.84,
          owner_memory_refs: [],
          owner_memory_topics: [],
        })}\n` +
        `${json({ type: 'content', content: 'Tail parsed response.' })}\n` +
        `${json({ type: 'done' })}`;

      await route.fulfill({
        status: 200,
        headers: {
          ...CORS_HEADERS,
          'content-type': 'application/x-ndjson',
        },
        body: payload,
      });
    });

    await page.goto('/dashboard/simulator/owner');

    const input = page.locator('textarea[aria-label="Chat message input"]');
    await input.fill('Parse tail chunk');
    await input.press('Enter');

    await expect(page.getByText('Tail parsed response.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'tail-owner.pdf' })).toBeVisible();
  });

  test('public share chat renders citation link', async ({ page }) => {
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
          response: 'Public citation response.',
          citations: ['src-public-1'],
          citation_details: [
            {
              id: 'src-public-1',
              filename: 'public-notes.txt',
              citation_url: 'https://example.com/public-notes.txt',
            },
          ],
          confidence_score: 0.88,
        }),
      });
    });

    await page.goto('/share/e2e-twin/token-e2e');
    await expect(page.getByRole('heading', { name: 'E2E Public Twin' })).toBeVisible();

    const input = page.getByPlaceholder('Type your message...');
    await input.fill('Share mode citation test');
    await input.press('Enter');

    await expect(page.getByText('Public citation response.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'public-notes.txt' })).toBeVisible();
    await expect(page.getByText('88%')).toBeVisible();
  });
});
