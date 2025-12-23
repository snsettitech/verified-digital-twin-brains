/**
 * Gate 6: Tenant Isolation E2E Tests
 * 
 * Verifies that tenant isolation is properly enforced:
 * - Tenant B cannot access Tenant A's graph data
 * - Tenant B cannot approve Tenant A's profiles
 * - Each tenant can only access their own data
 */
import { test, expect } from '@playwright/test';

const API_URL = 'http://localhost:8000';

// Simulated tenant tokens for testing
const TENANT_A_TOKEN = 'development_token';  // Tenant A (primary test user)
const TENANT_B_TOKEN = 'tenant_b_dev_token'; // Tenant B (unauthorized user)
const TENANT_A_TWIN = 'eeeed554-9180-4229-a9af-0f8dd2c69e9b';

test.describe('Gate 6: Tenant Isolation', () => {

    test.describe('API-Level Tenant Isolation', () => {

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

        test('Simulator page loads and shows chat interface', async ({ page }) => {
            await page.goto('/dashboard/simulator');

            // Check for chat elements
            await expect(page.locator('input[placeholder*="Ask"]')).toBeVisible();
        });

        test('Right Brain page loads with interview interface', async ({ page }) => {
            await page.goto('/dashboard/right-brain');

            // Check for interview elements
            await expect(page.locator('h1')).toContainText('Right Brain');
        });

        test('Brain Graph page loads with graph visualization', async ({ page }) => {
            await page.goto('/dashboard/brain');

            // Check for graph elements
            await expect(page.locator('h1')).toContainText('Brain Graph');
        });
    });

    test.describe('Health Checks', () => {

        test('Backend health endpoint returns online status', async ({ request }) => {
            const response = await request.get(`${API_URL}/health`);

            expect(response.status()).toBe(200);
            const data = await response.json();
            expect(data.status).toBe('online');
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
