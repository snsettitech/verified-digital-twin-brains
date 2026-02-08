/**
 * Gate 6: Tenant Isolation E2E Tests
 * 
 * Verifies that tenant isolation is properly enforced:
 * - Tenant B cannot access Tenant A's graph data
 * - Tenant B cannot approve Tenant A's profiles
 * - Each tenant can only access their own data
 */
import { test, expect } from '@playwright/test';
import path from 'path';

const API_URL = process.env.E2E_BACKEND_URL || 'http://localhost:8000';
const RUN_BACKEND_TESTS = process.env.RUN_BACKEND_E2E === '1';

// Simulated tenant tokens for testing (override via env for real runs)
const TENANT_A_TOKEN = process.env.E2E_TENANT_A_TOKEN || 'development_token';
const TENANT_B_TOKEN = process.env.E2E_TENANT_B_TOKEN || 'tenant_b_dev_token';
const TENANT_A_TWIN = process.env.E2E_TENANT_A_TWIN || 'eeeed554-9180-4229-a9af-0f8dd2c69e9b';

test.describe('Gate 6: Tenant Isolation', () => {

    test.describe('API-Level Tenant Isolation', () => {
        test.skip(!RUN_BACKEND_TESTS, 'Backend E2E env not configured');

        test('Tenant A can access their own graph data', async ({ request }) => {
            const response = await request.get(
                `${API_URL}/twins/${TENANT_A_TWIN}/graph`,
                { headers: { 'Authorization': `Bearer ${TENANT_A_TOKEN}` } }
            );

            expect(response.status()).toBe(200);
            const data = await response.json();
            expect(data).toHaveProperty('nodes');
            expect(data).toHaveProperty('edges');
        });

        test('Tenant A can access their profile versions', async ({ request }) => {
            const response = await request.get(
                `${API_URL}/cognitive/profiles/${TENANT_A_TWIN}/versions`,
                { headers: { 'Authorization': `Bearer ${TENANT_A_TOKEN}` } }
            );

            expect(response.status()).toBe(200);
            const data = await response.json();
            expect(data).toHaveProperty('versions');
        });

        test('Tenant B cannot access Tenant A graph data', async ({ request }) => {
            const response = await request.get(
                `${API_URL}/twins/${TENANT_A_TWIN}/graph`,
                { headers: { 'Authorization': `Bearer ${TENANT_B_TOKEN}` } }
            );

            // Should get 403 Forbidden or 401 Unauthorized
            expect([401, 403]).toContain(response.status());
        });

        test('Tenant B cannot approve Tenant A profile', async ({ request }) => {
            const response = await request.post(
                `${API_URL}/cognitive/profiles/${TENANT_A_TWIN}/approve`,
                {
                    headers: {
                        'Authorization': `Bearer ${TENANT_B_TOKEN}`,
                        'Content-Type': 'application/json'
                    },
                    data: { notes: 'Unauthorized approval attempt' }
                }
            );

            // Should get 403 Forbidden or 401 Unauthorized
            expect([401, 403]).toContain(response.status());
        });

        test('Tenant B cannot delete Tenant A versions', async ({ request }) => {
            const response = await request.delete(
                `${API_URL}/cognitive/profiles/${TENANT_A_TWIN}/versions/1`,
                { headers: { 'Authorization': `Bearer ${TENANT_B_TOKEN}` } }
            );

            // Should get 403 Forbidden or 401 Unauthorized
            expect([401, 403]).toContain(response.status());
        });

        test('Tenant B cannot read Tenant A version details', async ({ request }) => {
            const response = await request.get(
                `${API_URL}/cognitive/profiles/${TENANT_A_TWIN}/versions/1`,
                { headers: { 'Authorization': `Bearer ${TENANT_B_TOKEN}` } }
            );

            // Should get 403 Forbidden or 401 Unauthorized
            expect([401, 403]).toContain(response.status());
        });
    });

    test.describe('UI-Level Access Control', () => {

        test('Dashboard loads successfully for authenticated user', async ({ page }) => {
            await page.goto('/dashboard');

            // Check that page loads without error
            await expect(page.locator('h1')).toContainText('Dashboard');
        });

        test('Simulator page loads and shows training module', async ({ page }) => {
            await page.goto('/dashboard/simulator');

            await expect(page.getByRole('heading', { name: 'Training Module' })).toBeVisible();
            await expect(page.getByText('Step 5. Validate')).toBeVisible();
            await expect(page.locator('textarea[aria-label="Chat message input"]')).toBeVisible();
        });

        test('Right Brain page loads with training interview step', async ({ page }) => {
            await page.goto('/dashboard/right-brain');

            await expect(page.getByRole('heading', { name: 'Training Module' })).toBeVisible();
            await expect(page.getByText('Step 2. Interview')).toBeVisible();
        });

        test('Brain Graph page loads with graph visualization', async ({ page }) => {
            await page.goto('/dashboard/brain');

            // Check for graph elements
            await expect(page.locator('h1')).toContainText('Brain Graph');
        });

        test('Training knowledge modal exposes file input', async ({ page }) => {
            await page.goto('/dashboard/simulator');

            await page.getByRole('button', { name: 'Skip to Knowledge' }).click();
            await page.getByRole('button', { name: 'Add Knowledge' }).first().click();

            const fileInput = page.locator('input[type="file"]');
            await expect(fileInput).toHaveCount(1);

            const uploadButton = page.getByRole('button', { name: 'Upload', exact: true });
            await expect(uploadButton).toBeDisabled();

            const fixturePath = path.join(__dirname, '..', 'fixtures', 'sample.txt');
            await fileInput.setInputFiles(fixturePath);
            await expect(uploadButton).toBeEnabled();
        });
    });

    test.describe('Health Checks', () => {
        test.skip(!RUN_BACKEND_TESTS, 'Backend E2E env not configured');

        test('Backend health endpoint returns online status', async ({ request }) => {
            const response = await request.get(`${API_URL}/health`);

            expect(response.status()).toBe(200);
            const data = await response.json();
            expect(['online', 'healthy']).toContain(data.status);
        });

        test('Config endpoint returns specialization info', async ({ request }) => {
            const response = await request.get(`${API_URL}/config/specialization`);

            expect(response.status()).toBe(200);
            const data = await response.json();
            // Config returns the manifest with 'name' property (e.g., 'vanilla')
            expect(data).toHaveProperty('name');
            expect(data).toHaveProperty('features');
        });
    });
});
