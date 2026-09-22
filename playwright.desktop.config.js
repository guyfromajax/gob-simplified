// @ts-check
const { defineConfig, devices } = require('@playwright/test');

const PORT = process.env.PORT || '8767';

module.exports = defineConfig({
  testDir: './tests/e2e',
  testMatch: 'desktop-*.spec.js',
  timeout: 120 * 1000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.DESKTOP_BASE_URL || `http://127.0.0.1:${PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop-chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: process.env.PYTHON_PATH
      ? `${process.env.PYTHON_PATH} tests/e2e/helpers/seed_and_serve_desktop.py`
      : "sh -c '(.venv/bin/python tests/e2e/helpers/seed_and_serve_desktop.py) || (venv/bin/python tests/e2e/helpers/seed_and_serve_desktop.py) || python3 tests/e2e/helpers/seed_and_serve_desktop.py'",
    url: `http://127.0.0.1:${PORT}/app-config`,
    reuseExistingServer: process.env.PW_REUSE_SERVER === '1',
    timeout: 180 * 1000,
    env: {
      ...process.env,
      PORT,
      GOB_LOOPBACK_PORT: PORT,
    },
  },
});
