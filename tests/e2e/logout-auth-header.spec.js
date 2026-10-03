// @ts-check
/**
 * Logout must send the bearer token. Since fix/auth-hardening the server only
 * revokes the session (bumps token_version — signs out everywhere) when the
 * POST /api/auth/logout carries an Authorization header. The three callers
 * (mode-select.js, gobSettings.js, authBarInit.js) now go through the one shared
 * helper API_CONFIG.logout(), which attaches the header BEFORE clearing the local
 * token. This proves the header is present and the token is cleared afterward, and
 * that with no reachable server (desktop/offline) it still clears without crashing.
 */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

test.describe('logout sends the bearer token', () => {
  test('POST /api/auth/logout carries Authorization, then the local token is cleared', async ({ page }) => {
    await stubAuth(page); // sets auth_token = 'e2e-stub-token'
    let seenAuth = null;
    let method = null;
    await page.route('**/api/auth/logout', async (route) => {
      seenAuth = route.request().headers()['authorization'] || null;
      method = route.request().method();
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    });

    await page.goto('/mode-select.html');
    await page.waitForFunction(() => !!(window.API_CONFIG && typeof window.API_CONFIG.logout === 'function'));

    await page.evaluate(() => window.API_CONFIG.logout());
    await expect.poll(() => seenAuth).toBe('Bearer e2e-stub-token');
    expect(method).toBe('POST');

    const stored = await page.evaluate(() => ({
      token: localStorage.getItem('auth_token'),
      user: localStorage.getItem('auth_user'),
    }));
    expect(stored.token).toBeNull();
    expect(stored.user).toBeNull();
  });

  test('with no reachable server the token still clears and nothing throws (desktop/offline)', async ({ page }) => {
    await stubAuth(page);
    await page.route('**/api/auth/logout', (route) => route.abort());

    await page.goto('/mode-select.html');
    await page.waitForFunction(() => !!(window.API_CONFIG && typeof window.API_CONFIG.logout === 'function'));

    const result = await page.evaluate(async () => {
      let threw = false;
      try { await window.API_CONFIG.logout(); } catch (e) { threw = true; }
      return { threw, token: localStorage.getItem('auth_token') };
    });
    expect(result.threw).toBe(false);
    expect(result.token).toBeNull();
  });
});
