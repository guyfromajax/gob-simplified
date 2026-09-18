const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const SRC = fs.readFileSync(
  path.join(__dirname, '../../FrontEnd/static/js/config/api-config.js'),
  'utf8',
);

test.describe('WS-5a routing seam', () => {
  test('web profile is remote; desktop + local splits routable vs always-remote', async ({ page }) => {
    await page.addInitScript({ content: SRC });
    await page.goto('about:blank');

    const out = await page.evaluate(() => {
      const api = window.API_CONFIG;
      const remote = api._resolveBaseUrl(window.location.hostname);
      const noArgs = api.getBaseUrl();
      const webLocalFranchise = api.getBaseUrl({ category: 'franchise', runtime: 'local' });
      const webLocalAuth = api.getBaseUrl({ category: 'auth', runtime: 'local' });

      window.GOB_BUILD_PROFILE = 'desktop';
      const hostedFranchise = api.getBaseUrl({ category: 'franchise', runtime: 'hosted' });
      const localFranchise = api.getBaseUrl({ category: 'franchise', runtime: 'local' });
      const localAuth = api.getBaseUrl({ category: 'auth', runtime: 'local' });
      const localBilling = api.getBaseUrl({ category: 'billing', runtime: 'local' });
      const stillNoArgs = api.getBaseUrl();

      return {
        remote,
        noArgs,
        webLocalFranchise,
        webLocalAuth,
        hostedFranchise,
        localFranchise,
        localAuth,
        localBilling,
        stillNoArgs,
      };
    });

    expect(out.noArgs).toBe(out.remote);
    expect(out.webLocalFranchise).toBe(out.remote);
    expect(out.webLocalAuth).toBe(out.remote);
    expect(out.hostedFranchise).toBe(out.remote);
    expect(out.stillNoArgs).toBe(out.remote);
    expect(out.localFranchise).toBe('http://127.0.0.1:8000');
    expect(out.localAuth).toBe(out.remote);
    expect(out.localBilling).toBe(out.remote);
  });
});
