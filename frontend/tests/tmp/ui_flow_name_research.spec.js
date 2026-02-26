import { test } from '@playwright/test';

test('deep research ui flow with Sainath Setti', async ({ page }) => {
  const events = [];
  page.on('console', msg => events.push(`[${msg.type()}] ${msg.text()}`));

  await page.goto('http://127.0.0.1:3000/dashboard/deep-research');
  await page.waitForTimeout(1500);

  const title = await page.locator('h1').first().innerText();
  console.log('TITLE=' + title);

  await page.fill('input[placeholder="e.g. Satya Nadella"]', 'Sainath Setti');
  await page.click('button:has-text("Start research")');

  await page.waitForTimeout(8000);

  const runIdVisible = await page.locator('text=Run ID:').first().isVisible().catch(() => false);
  const errorText = await page.locator('div.text-red-300').first().innerText().catch(() => null);
  const hasSearching = await page.locator('text=searching').first().isVisible().catch(() => false);

  console.log('RUN_ID_VISIBLE=' + runIdVisible);
  console.log('HAS_SEARCHING=' + hasSearching);
  console.log('ERROR_TEXT=' + (errorText || 'null'));
  console.log('CONSOLE_ERRORS=' + events.filter(e => e.startsWith('[error]')).length);

  await page.screenshot({ path: 'd:/verified-digital-twin-brains/artifacts/deep-research-ui-flow.png', fullPage: true });
});



