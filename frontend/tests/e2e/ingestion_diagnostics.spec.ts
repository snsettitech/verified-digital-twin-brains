import { test, expect } from '@playwright/test';

const BACKEND_GLOB = '**';

test.describe('Ingestion Diagnostics (UI)', () => {
  test('Submit YouTube URL -> reaches terminal error -> diagnostics shows details', async ({ page }) => {
    const youtubeUrl = 'https://www.youtube.com/watch?v=HiC1J8a9V1I';
    const twinId = 'e2e-twin';
    const sourceId = 'src-youtube-1';

    let ingestSubmitted = false;
    let sourcesCall = 0;

    const json = (obj: unknown) => JSON.stringify(obj);

    await page.route(`${BACKEND_GLOB}/ingest/url/${twinId}`, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({
          status: 204,
          headers: {
            'access-control-allow-origin': '*',
            'access-control-allow-methods': 'GET,POST,OPTIONS',
            'access-control-allow-headers': 'authorization,content-type',
          },
          body: '',
        });
        return;
      }

      ingestSubmitted = true;
      sourcesCall = 0;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: {
          'access-control-allow-origin': '*',
          'access-control-allow-headers': 'authorization,content-type',
        },
        body: json({ source_id: sourceId, job_id: 'job-1', status: 'pending' }),
      });
    });

    await page.route(`${BACKEND_GLOB}/sources/${twinId}`, async (route) => {
      if (!ingestSubmitted) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: {
            'access-control-allow-origin': '*',
          },
          body: json([]),
        });
        return;
      }

      sourcesCall += 1;

      // Progression: pending -> error (fast, deterministic)
      const status = sourcesCall <= 1 ? 'pending' : 'error';

      const lastStep =
        status === 'pending' ? 'queued' : 'fetching';

      const payload = [
        {
          id: sourceId,
          twin_id: twinId,
          filename: 'YouTube: queued',
          citation_url: youtubeUrl,
          status,
          last_provider: 'youtube',
          last_step: lastStep,
          last_event_at: new Date().toISOString(),
          last_error:
            status === 'error'
              ? {
                  code: 'YOUTUBE_TRANSCRIPT_UNAVAILABLE',
                  message: 'No transcript could be extracted. This video may not have captions.',
                  provider: 'youtube',
                  step: 'fetching',
                  http_status: 403,
                  retryable: false,
                }
              : null,
        },
      ];

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: {
          'access-control-allow-origin': '*',
        },
        body: json(payload),
      });
    });

    await page.route(`${BACKEND_GLOB}/sources/${sourceId}/events`, async (route) => {
      const now = new Date().toISOString();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: {
          'access-control-allow-origin': '*',
        },
        body: json([
          {
            id: 'ev-1',
            provider: 'youtube',
            step: 'queued',
            status: 'completed',
            message: 'queued',
            started_at: now,
          },
          {
            id: 'ev-2',
            provider: 'youtube',
            step: 'fetching',
            status: 'error',
            message: 'Fetching YouTube transcript/captions',
            error: {
              code: 'YOUTUBE_TRANSCRIPT_UNAVAILABLE',
              message: 'No transcript could be extracted. This video may not have captions.',
              provider: 'youtube',
              step: 'fetching',
              http_status: 403,
              retryable: false,
            },
            started_at: now,
          },
        ]),
      });
    });

    await page.route(`${BACKEND_GLOB}/sources/${sourceId}/logs`, async (route) => {
      const now = new Date().toISOString();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: {
          'access-control-allow-origin': '*',
        },
        body: json([
          {
            id: 'log-1',
            log_level: 'error',
            message: 'YouTube transcript unavailable',
            metadata: { video_id: 'HiC1J8a9V1I' },
            created_at: now,
          },
        ]),
      });
    });

    await page.goto('/dashboard/simulator');

    await page.getByRole('button', { name: 'Skip to Knowledge' }).click();

    const urlInput = page.locator('input[type="url"]');
    await urlInput.fill(youtubeUrl);
    await page.getByRole('button', { name: 'Add URL' }).click();

    // Row should eventually show error state + the error summary text
    await expect(page.getByText('YOUTUBE_TRANSCRIPT_UNAVAILABLE').first()).toBeVisible();

    await page.getByRole('button', { name: 'Diagnostics' }).click();

    await expect(page.getByText('Last Error')).toBeVisible();
    await expect(page.getByText('Step Timeline')).toBeVisible();
    await expect(page.getByText('Ingestion Logs')).toBeVisible();

    // Meaningful content (not empty placeholders)
    await expect(page.getByText('YOUTUBE_TRANSCRIPT_UNAVAILABLE').first()).toBeVisible();
    await expect(page.getByText('[error]')).toBeVisible();
  });
});
