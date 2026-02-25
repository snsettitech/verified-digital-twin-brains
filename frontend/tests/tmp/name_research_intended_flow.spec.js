const { test } = require('@playwright/test');

test('intended production flow: login -> start run -> poll', async ({ page }) => {
  test.setTimeout(600000);
  const email = process.env.TEST_ACCOUNT_EMAIL;
  const password = process.env.TEST_ACCOUNT_PASSWORD;
  if (!email || !password) {
    throw new Error('Missing TEST_ACCOUNT_EMAIL / TEST_ACCOUNT_PASSWORD env vars');
  }

  const logs = [];
  page.on('console', (msg) => logs.push(`[${msg.type()}] ${msg.text()}`));

  await page.goto('http://127.0.0.1:3000/auth/login?redirect=%2Fdashboard%2Fdeep-research', {
    waitUntil: 'domcontentloaded',
  });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button:has-text("Sign in")');

  await page.waitForTimeout(2500);
  const loginError = await page.locator('div:has-text("Invalid")').first().textContent().catch(() => null);

  if (!page.url().includes('/dashboard/deep-research')) {
    await page.goto('http://127.0.0.1:3000/dashboard/deep-research', { waitUntil: 'domcontentloaded' });
  }

  await page.waitForTimeout(1500);
  await page.fill('input[placeholder="e.g. Satya Nadella"]', 'Sainath Setti');
  await page.click('button:has-text("Start research")');

  await page.waitForTimeout(5000);

  const runIdText = await page.locator('text=Run ID:').first().textContent().catch(() => null);
  const errorText = await page.locator('div.text-red-300').first().textContent().catch(() => null);

  let terminal = 'unknown';
  let sawCrawling = false;
  let sawSynthesizing = false;
  if (runIdText) {
    for (let i = 0; i < 120; i += 1) {
      await page.waitForTimeout(2500);
      const hasCrawling = await page.locator('text=crawling').first().isVisible().catch(() => false);
      const hasSynthesizing = await page.locator('text=synthesizing').first().isVisible().catch(() => false);
      if (hasCrawling) sawCrawling = true;
      if (hasSynthesizing) sawSynthesizing = true;

      const hasDownload = await page
        .locator('button:has-text("Download JSON")')
        .isVisible()
        .catch(() => false);
      const hasFailed = await page.locator('text=failed').first().isVisible().catch(() => false);
      if (hasDownload) {
        terminal = 'completed';
        break;
      }
      if (hasFailed) {
        terminal = 'failed';
        break;
      }
    }
  }

  const finalErrorText = await page.locator('div.text-red-300').first().textContent().catch(() => null);

  console.log(`LOGIN_ERROR=${loginError || 'null'}`);
  console.log(`URL=${page.url()}`);
  console.log(`RUN_ID_TEXT=${runIdText || 'null'}`);
  console.log(`SAW_CRAWLING=${sawCrawling}`);
  console.log(`SAW_SYNTHESIZING=${sawSynthesizing}`);
  console.log(`ERROR_TEXT=${errorText || 'null'}`);
  console.log(`TERMINAL=${terminal}`);
  console.log(`FINAL_ERROR=${finalErrorText || 'null'}`);
  console.log(`CONSOLE_ERROR_COUNT=${logs.filter((x) => x.startsWith('[error]')).length}`);

  await page.screenshot({
    path: 'd:/verified-digital-twin-brains/artifacts/deep-research-intended-flow.png',
    fullPage: true,
  });
});
