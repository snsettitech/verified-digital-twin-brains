import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.E2E_BASE_URL || 'http://localhost:3000';
const useExternalBaseUrl = Boolean(process.env.E2E_BASE_URL);
const traceMode = process.env.PW_TRACE_MODE || (process.env.CI ? 'retain-on-failure' : 'on-first-retry');
const reporter = process.env.PW_REPORTER || 'html';

export default defineConfig({
    testDir: './tests/e2e',
    outputDir: './playwright-test-results',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: 1,
    reporter,
    use: {
        baseURL,
        trace: traceMode as 'on-first-retry' | 'retain-on-failure' | 'on' | 'off',
        screenshot: 'only-on-failure',
    },

    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],

    webServer: useExternalBaseUrl
        ? undefined
        : {
              command: 'npx next dev --webpack',
              url: 'http://localhost:3000',
              reuseExistingServer: false,
              timeout: 120000,
              env: {
                  E2E_BYPASS_AUTH: '1',
                  NEXT_PUBLIC_E2E_BYPASS_AUTH: '1',
                  NEXT_PUBLIC_BACKEND_URL: 'http://localhost:8000',
                  NEXT_PUBLIC_API_URL: 'http://localhost:8000',
              },
          },
});
