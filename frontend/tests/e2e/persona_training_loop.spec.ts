import { expect, test } from '@playwright/test';

import {
  createTrainingHarnessState,
  registerTrainingModuleRoutes,
} from './helpers/personaHarness';

test.describe('Persona Training Loop (UI)', () => {
  test('owner training session toggles simulator chat payload between training and owner', async ({ page }) => {
    const state = createTrainingHarnessState();
    await registerTrainingModuleRoutes(page, state);

    await page.goto('/dashboard/simulator');

    await expect(page.getByRole('heading', { name: 'Training Module' })).toBeVisible();
    await expect(page.getByText('Step 5. Validate')).toBeVisible();
    await expect(page.getByText('Owner Training Session')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Start Training' })).toBeVisible();

    await page.getByRole('button', { name: 'Start Training' }).click();
    await expect(page.getByText('Active (ts-e2e-1)')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Stop Training' })).toBeVisible();
    expect(state.startCalls).toBe(1);

    const input = page.locator('textarea[aria-label="Chat message input"]');
    await input.fill('Use training mode for this answer');
    await input.press('Enter');
    await expect(page.getByText('Training context answer.')).toBeVisible();

    await expect.poll(() => state.ownerChatBodies.length).toBe(1);
    expect(state.ownerChatBodies[0].mode).toBe('training');
    expect(state.ownerChatBodies[0].training_session_id).toBe('ts-e2e-1');

    await page.getByRole('button', { name: 'Stop Training' }).click();
    await expect(page.getByText('Inactive. Start to capture training-context turns.')).toBeVisible();
    expect(state.stopCalls).toBe(1);

    await input.fill('Now send as owner chat');
    await input.press('Enter');
    await expect(page.getByText('Owner chat answer.')).toBeVisible();

    await expect.poll(() => state.ownerChatBodies.length).toBe(2);
    expect(state.ownerChatBodies[1].mode).toBe('owner');
    expect(state.ownerChatBodies[1].training_session_id).toBeUndefined();
  });
});

