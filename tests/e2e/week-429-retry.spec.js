// @ts-check
/**
 * The rate-limited week routes (complete-week/phase-a/phase-b, start-cpu-sims,
 * finish-season) now go through API_CONFIG.fetchWithRateLimitRetry, which on a 429
 * reads Retry-After, waits, and re-sends the same request — no error UI, the caller
 * just sees the eventual success. This drives the real phase-b client: the endpoint
 * 429s once (Retry-After: 1) then 200; the advance completes with exactly 2 requests
 * and no error surfaced.
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

test.describe('week routes ride out a 429', () => {
  test('a single 429 (Retry-After: 1) is retried; the call completes in exactly 2 requests', async ({ page }) => {
    await stubAuth(page);
    let hits = 0;
    await page.route('**/franchise/complete-week/phase-b', async (route) => {
      hits += 1;
      if (hits === 1) {
        await route.fulfill({
          status: 429,
          headers: { 'Retry-After': '1' },
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Rate limit exceeded. Please try again in 1 seconds.' }),
        });
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
      }
    });

    await page.goto('/mode-select.html');
    await page.waitForFunction(() => !!(window.API_CONFIG && typeof window.API_CONFIG.fetchWithRateLimitRetry === 'function'));

    // Surface any uncaught error / alert as a failure signal ("no error UI").
    let pageError = null;
    page.on('pageerror', (err) => { pageError = err; });
    page.on('dialog', (d) => { pageError = new Error('unexpected dialog: ' + d.message()); d.dismiss().catch(() => {}); });

    const result = await page.evaluate(async () => {
      const mod = await import('/js/phaser/utils/franchisePhaseBClient.js');
      const res = await mod.getOrStartFranchisePhaseB({ franchise_id: 'f-429', week: 22 });
      return { status: res.status, ok: res.ok };
    });

    expect(result.ok).toBe(true);
    expect(result.status).toBe(200);
    expect(hits).toBe(2);
    expect(pageError).toBeNull();
  });
});
