const { test, expect } = require('@playwright/test');

/**
 * Marketing home: public (authGuard), nav + auth chrome, auth assets load.
 * Covers the canonical /homepage.html. The homepage-v3.html copy was deleted on 2026-10-01
 * (Jamie's ruling #10); jamie-rulings-batch.spec.js checks it is gone.
 */

function marketingPaths() {
  return ['/static/homepage.html'];
}

test.describe('homepage (v3 design) — public access & auth UI', () => {
  for (const path of marketingPaths()) {
    test(`unauthenticated: no login redirect (${path})`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState('domcontentloaded');
      await expect(page).not.toHaveURL(/\/login\.html/);
    });

    test(`auth bar + logged-out links (${path})`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('#auth-bar')).toBeVisible();
      await expect(page.locator('#auth-logged-out')).toBeVisible();
      await expect(page.locator('#auth-logged-out a[href*="login"]')).toBeVisible();
      await expect(page.locator('#auth-logged-out a[href*="signup"]')).toBeVisible();
    });
  }

  test('authGuard / authBarInit not 404 on main homepage', async ({ page }) => {
    const failed = [];
    page.on('response', (res) => {
      const u = res.url();
      if (
        (u.includes('authGuard.js') || u.includes('authBarInit.js')) &&
        res.status() === 404
      ) {
        failed.push(u);
      }
    });
    await page.goto('/static/homepage.html');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    expect(failed, `404 on auth assets: ${failed.join(', ')}`).toHaveLength(0);
  });
});
