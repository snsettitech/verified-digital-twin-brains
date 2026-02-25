// Minimal config to run against already-running local app
/** @type {import('@playwright/test').PlaywrightTestConfig} */
module.exports = {
  testDir: 'd:/verified-digital-twin-brains/artifacts',
  timeout: 120000,
  retries: 0,
  workers: 1,
  use: {
    headless: true,
    viewport: { width: 1440, height: 900 },
  },
};
