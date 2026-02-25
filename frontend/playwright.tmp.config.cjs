/** @type {import('@playwright/test').PlaywrightTestConfig} */
module.exports = {
  testDir: './tests/tmp',
  timeout: 120000,
  retries: 0,
  workers: 1,
  use: { headless: true, viewport: { width: 1440, height: 900 } },
};
