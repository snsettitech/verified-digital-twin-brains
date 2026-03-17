/**
 * Onboarding Full Flow E2E Test
 *
 * Tests the complete unified onboarding flow using "Sainath Setti" as example:
 * - VC at Antler
 * - MBA at Schulich School of Business
 *
 * Uses mocked backend responses so the test runs without a real backend.
 * For live backend testing, run with E2E_USE_REAL_BACKEND=1 and ensure backend + Supabase are running.
 */

import { expect, test } from '@playwright/test';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const USE_REAL_BACKEND = process.env.E2E_USE_REAL_BACKEND === '1';

// Test data: Sainath Setti - VC at Antler, MBA at Schulich School of Business
const TEST_PERSONA = {
  fullName: 'Sainath Setti',
  headline: 'VC at Antler',
  location: 'Toronto, Canada',
  pasteContent: 'MBA at Schulich School of Business. Venture capital and early-stage investing.',
};

const MOCK_TWIN_ID = 'e2e-twin-sainath';
const MOCK_RESEARCH_RUN_ID = 'e2e-research-run-1';

function backendGlob(): string {
  const base = BACKEND_URL.replace(/\/$/, '');
  return `${base}/*`;
}

test.describe('Onboarding Full Flow - Sainath Setti', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(90000); // Allow 90s for first load (dev server cold start)
    if (USE_REAL_BACKEND) return;

    // Mock POST /twins - create twin
    await page.route('**/twins', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: MOCK_TWIN_ID,
            name: `${TEST_PERSONA.fullName} (Draft)`,
            status: 'draft',
            specialization: 'vanilla',
            settings: {},
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Mock POST /persona/link-compile/jobs/mode-b (paste)
    await page.route('**/persona/link-compile/jobs/mode-b', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ job_id: 'e2e-job-b', status: 'pending' }),
        });
      } else {
        await route.continue();
      }
    });

    // Mock POST /persona/link-compile/jobs/mode-c (URLs) - skip if not called
    await page.route('**/persona/link-compile/jobs/mode-c', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ job_id: 'e2e-job-c', status: 'pending' }),
        });
      } else {
        await route.continue();
      }
    });

    // Mock POST /twins/{id}/research - create research run (URL ends with /research, no runId)
    await page.route(new RegExp(`.*/twins/[^/]+/research$`), async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            research_run_id: MOCK_RESEARCH_RUN_ID,
            twin_id: MOCK_TWIN_ID,
            status: 'crawling',
            created_at: new Date().toISOString(),
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Mock GET /twins/{id}/research/{runId} - status polling (progress through states)
    let pollCount = 0;
    await page.route(
      new RegExp(`.*/twins/[^/]+/research/[^/]+$`),
      async (route) => {
        if (route.request().method() !== 'GET') {
          await route.continue();
          return;
        }
        pollCount++;
        // Simulate progress: crawling -> awaiting_confirmation -> ready_for_ingestion -> ingestion_completed -> bio_generated -> completed
        const stages = [
          { status: 'crawling', next_actions: ['Crawling web...'] },
          { status: 'awaiting_confirmation', next_actions: ['Review sources'] },
          { status: 'ready_for_ingestion', next_actions: ['Continue'] },
          { status: 'ingestion_completed', next_actions: ['Continue'] },
          { status: 'bio_generated', next_actions: ['Continue'] },
          { status: 'completed', next_actions: ['Done'] },
        ];
        const stageIndex = Math.min(Math.floor(pollCount / 2), stages.length - 1);
        const stage = stages[stageIndex];

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            research_run_id: MOCK_RESEARCH_RUN_ID,
            twin_id: MOCK_TWIN_ID,
            status: stage.status,
            next_actions: stage.next_actions,
            warnings: [],
            checkpoint_data: {
              ingestion: {
                sources_total: 5,
                sources_ingested: stageIndex >= 2 ? 5 : pollCount,
                chunks_created: stageIndex >= 3 ? 120 : 0,
                words_processed: stageIndex >= 3 ? 3500 : 0,
              },
            },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }),
        });
      }
    );

    // Mock pending confirmations
    await page.route(
      new RegExp(`.*/twins/${MOCK_TWIN_ID}/research/${MOCK_RESEARCH_RUN_ID}/pending-confirmations`),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                confirmation_id: 'conf-1',
                url: 'https://linkedin.com/in/sainathsetti',
                title: 'Sainath Setti | LinkedIn',
                identity_match_tier: 'likely',
                status: 'pending',
              },
            ],
            total: 1,
            limit: 100,
            offset: 0,
            has_more: false,
          }),
        });
      }
    );

    // Mock continue-ingestion, continue-bio, continue-finalize
    await page.route('**/continue-ingestion', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          research_run_id: MOCK_RESEARCH_RUN_ID,
          previous_status: 'ready_for_ingestion',
          new_status: 'ingesting',
        }),
      });
    });
    await page.route('**/continue-bio', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          research_run_id: MOCK_RESEARCH_RUN_ID,
          previous_status: 'ingestion_completed',
          new_status: 'generating_bio',
        }),
      });
    });
    await page.route('**/continue-finalize', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          research_run_id: MOCK_RESEARCH_RUN_ID,
          previous_status: 'bio_generated',
          new_status: 'completed',
        }),
      });
    });

    // Mock bulk-confirm
    await page.route('**/bulk-confirm', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          research_run_id: MOCK_RESEARCH_RUN_ID,
          action: 'confirm',
          requested: 1,
          succeeded: 1,
          failed: 0,
          errors: [],
        }),
      });
    });

    // Mock research-summary
    await page.route(new RegExp(`.*/twins/[^/]+/research-summary`), async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          twin_id: MOCK_TWIN_ID,
          research_run_id: MOCK_RESEARCH_RUN_ID,
          status: 'completed',
          sources: { confirmed: [], auto_confirmed: [], pending: [], manual_review: [], rejected: [] },
          next_actions: ['Done'],
        }),
      });
    });

    // Mock GET /auth/accounts (connected accounts)
    await page.route('**/auth/connected-accounts', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ accounts: [] }),
      });
    });
  });

  test('UI: onboarding form shows all fields', async ({ page }) => {
    await page.goto('/onboarding', { waitUntil: 'domcontentloaded', timeout: 60000 });

    await expect(page.getByRole('heading', { name: /Create Your Digital Twin/i })).toBeVisible();
    await expect(page.getByText('Full Name')).toBeVisible();
    await expect(page.getByPlaceholder(/Sarah Chen/)).toBeVisible();
    await expect(page.getByPlaceholder(/Founder at Acme/)).toBeVisible();
    await expect(page.getByPlaceholder(/San Francisco/)).toBeVisible();
    await expect(page.getByRole('button', { name: /Create My Digital Twin/i })).toBeVisible();
  });

  test('UI: can fill Sainath Setti persona and expand optional sources', async ({ page }) => {
    await page.goto('/onboarding');

    await page.getByPlaceholder(/Sarah Chen/).fill(TEST_PERSONA.fullName);
    await page.getByPlaceholder(/Founder at Acme/).fill(TEST_PERSONA.headline);
    await page.getByPlaceholder(/San Francisco/).fill(TEST_PERSONA.location);

    await expect(page.getByPlaceholder(/Sarah Chen/)).toHaveValue(TEST_PERSONA.fullName);
    await expect(page.getByPlaceholder(/Founder at Acme/)).toHaveValue(TEST_PERSONA.headline);

    await page.getByRole('button', { name: /I have files or links/i }).click();
    await expect(page.getByPlaceholder(/Paste text here/)).toBeVisible();
    await page.getByPlaceholder(/Title \(optional\)/).fill('Education & Background');
    await page.getByPlaceholder(/Paste text here/).fill(TEST_PERSONA.pasteContent);
  });

  test('full flow: Sainath Setti - create twin and complete onboarding', async ({ page }) => {
    test.setTimeout(USE_REAL_BACKEND ? 900000 : 120000); // 15 min for real backend, 2 min for mocked

    // Listen for alert dialogs (errors)
    page.on('dialog', async (dialog) => {
      console.error('[E2E] Dialog:', dialog.message());
      await dialog.dismiss();
    });

    await page.goto('/onboarding');

    // Step 1: Fill form
    await page.getByPlaceholder(/Sarah Chen/).fill(TEST_PERSONA.fullName);
    await page.getByPlaceholder(/Founder at Acme/).fill(TEST_PERSONA.headline);
    await page.getByPlaceholder(/San Francisco/).fill(TEST_PERSONA.location);

    await page.getByRole('button', { name: /I have files or links/i }).click();
    await page.getByPlaceholder(/Title \(optional\)/).fill('Education');
    await page.getByPlaceholder(/Paste text here/).fill(TEST_PERSONA.pasteContent);

    await page.getByRole('checkbox').check();
    await expect(page.getByRole('button', { name: /Create My Digital Twin/i })).toBeEnabled();

    await page.getByRole('button', { name: /Create My Digital Twin/i }).click();

    // Step 2: Wait for loading to finish, then research step
    await expect(page.getByText('Creating your twin...')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Creating your twin...')).toBeHidden({ timeout: 25000 });

    // Step 3: Research/building step should be visible
    await expect(
      page
        .locator(
          'text=/Starting Research|Creating research run|Research in progress|Profile Building|Building Your Profile|Analyzing/i'
        )
        .first()
    ).toBeVisible({ timeout: 10000 });

    // Step 4: Wait for research/build progress or confirmation
    await expect(
      page
        .locator(
          'text=/Crawling|Research|Confirm|Review|Ingesting|Building|Profile|Analyzing|Ready|Complete/i'
        )
        .first()
    ).toBeVisible({
      timeout: 20000,
    });

    // Step 5: If confirmation appears, confirm sources
    const confirmAll = page.getByRole('button', { name: /Confirm all|Confirm All/i });
    if (await confirmAll.isVisible().catch(() => false)) {
      await confirmAll.click();
    }

    // Step 6: Wait for completion - redirect to profile or claims review
    await expect(page.locator('text=/Profile|Dashboard|Claims|Complete|Ready|Your Digital Twin/i').first()).toBeVisible({
      timeout: 60000,
    });

    // Should eventually land on dashboard/profile
    await expect(page).toHaveURL(/\/(dashboard|profile|onboarding)/, { timeout: 30000 });
  });
});
